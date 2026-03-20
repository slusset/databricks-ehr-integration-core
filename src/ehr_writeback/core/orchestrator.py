"""Write-back orchestrator — the conductor that ties everything together.

Responsibilities:
1. Accept a batch of Observations
2. Check idempotency (skip already-processed)
3. Write to EHR adapter
4. Record results in idempotency store
5. Retry transient failures with exponential backoff
6. Dead-letter observations that exhaust retries
7. Circuit-break when the EHR endpoint is unhealthy

Closes #2.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum

from ehr_writeback.core.models import (
    DeadLetter,
    EHRSystem,
    Observation,
    WritebackResult,
    WritebackStatus,
)
from ehr_writeback.core.ports import (
    DeadLetterPort,
    EHRWritebackPort,
    IdempotencyPort,
)

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # normal operation
    OPEN = "open"  # failing, reject fast
    HALF_OPEN = "half_open"  # testing recovery


@dataclass
class RetryPolicy:
    """Configurable retry behavior."""

    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    exponential_base: float = 2.0

    def delay_for_attempt(self, attempt: int) -> float:
        """Exponential backoff with cap."""
        delay = self.base_delay_seconds * (self.exponential_base**attempt)
        return min(delay, self.max_delay_seconds)


@dataclass
class CircuitBreaker:
    """Simple circuit breaker for EHR endpoint health."""

    failure_threshold: int = 5
    recovery_timeout_seconds: float = 60.0
    _state: CircuitState = field(default=CircuitState.CLOSED)
    _failure_count: int = field(default=0)
    _last_failure_time: float = field(default=0.0)

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.recovery_timeout_seconds:
                self._state = CircuitState.HALF_OPEN
        return self._state

    def record_success(self) -> None:
        self._failure_count = 0
        self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                "Circuit breaker OPEN after %d failures",
                self._failure_count,
            )

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN


@dataclass
class BatchResult:
    """Summary of a batch write-back run."""

    succeeded: list[WritebackResult] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # idempotency keys
    failed: list[WritebackResult] = field(default_factory=list)
    dead_lettered: list[DeadLetter] = field(default_factory=list)

    @property
    def total(self) -> int:
        return (
            len(self.succeeded)
            + len(self.skipped)
            + len(self.failed)
            + len(self.dead_lettered)
        )

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return len(self.succeeded) / self.total


def default_idempotency_key(obs: Observation) -> str:
    """Generate a default idempotency key from observation fields."""
    raw = f"{obs.patient_id}:{obs.code}:{obs.effective_datetime.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()


@dataclass
class WritebackOrchestrator:
    """Orchestrates the write-back of observations to an EHR.

    Inject the ports at construction time — the orchestrator
    doesn't know or care which EHR system or storage backend
    is behind them.
    """

    ehr_adapter: EHRWritebackPort
    ehr_system: EHRSystem
    idempotency_store: IdempotencyPort
    dead_letter_store: DeadLetterPort
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    circuit_breaker: CircuitBreaker = field(
        default_factory=CircuitBreaker,
    )
    max_concurrency: int = 5

    async def process_batch(
        self,
        observations: list[Observation],
    ) -> BatchResult:
        """Process a batch of observations with concurrency control."""
        semaphore = asyncio.Semaphore(self.max_concurrency)
        result = BatchResult()

        async def _process_one(obs: Observation) -> None:
            async with semaphore:
                await self._process_single(obs, result)

        tasks = [_process_one(obs) for obs in observations]
        await asyncio.gather(*tasks)

        logger.info(
            "Batch complete: %d succeeded, %d skipped, "
            "%d failed, %d dead-lettered (%.0f%% success rate)",
            len(result.succeeded),
            len(result.skipped),
            len(result.failed),
            len(result.dead_lettered),
            result.success_rate * 100,
        )
        return result

    async def _process_single(
        self,
        observation: Observation,
        result: BatchResult,
    ) -> None:
        """Process one observation: dedup → write → record → retry/DLQ."""
        idem_key = default_idempotency_key(observation)

        # 1. Idempotency check
        if await self.idempotency_store.has_been_processed(idem_key):
            logger.debug("Skipping already-processed: %s", idem_key)
            result.skipped.append(idem_key)
            return

        # 2. Circuit breaker check
        if self.circuit_breaker.is_open:
            logger.warning(
                "Circuit open — dead-lettering %s",
                idem_key,
            )
            dead_letter = DeadLetter(
                observation=observation,
                idempotency_key=idem_key,
                ehr_system=self.ehr_system,
                last_error="Circuit breaker open",
                retry_count=0,
            )
            await self.dead_letter_store.send_to_dead_letter(dead_letter)
            result.dead_lettered.append(dead_letter)
            return

        # 3. Write with retry
        last_result: WritebackResult | None = None
        for attempt in range(self.retry_policy.max_retries + 1):
            wb_result = await self.ehr_adapter.write_observation(
                observation,
            )
            wb_result.retry_count = attempt

            if wb_result.status == WritebackStatus.SUCCESS:
                self.circuit_breaker.record_success()
                wb_result.idempotency_key = idem_key
                await self.idempotency_store.mark_processed(wb_result)
                result.succeeded.append(wb_result)
                logger.debug(
                    "Success: %s (attempt %d)",
                    idem_key,
                    attempt + 1,
                )
                return

            # Failed — record and maybe retry
            last_result = wb_result
            self.circuit_breaker.record_failure()

            if attempt < self.retry_policy.max_retries:
                delay = self.retry_policy.delay_for_attempt(attempt)
                logger.info(
                    "Retry %d/%d for %s in %.1fs: %s",
                    attempt + 1,
                    self.retry_policy.max_retries,
                    idem_key,
                    delay,
                    wb_result.error_message,
                )
                await asyncio.sleep(delay)

                # Re-check circuit before retrying
                if self.circuit_breaker.is_open:
                    break

        # 4. Exhausted retries — dead-letter
        error_msg = (
            last_result.error_message or "Unknown error"
            if last_result
            else "Unknown error"
        )
        dead_letter = DeadLetter(
            observation=observation,
            idempotency_key=idem_key,
            ehr_system=self.ehr_system,
            last_error=error_msg,
            retry_count=self.retry_policy.max_retries,
        )
        await self.dead_letter_store.send_to_dead_letter(dead_letter)
        result.dead_lettered.append(dead_letter)
        logger.warning(
            "Dead-lettered %s after %d attempts: %s",
            idem_key,
            self.retry_policy.max_retries + 1,
            error_msg,
        )

    async def process_single(
        self,
        observation: Observation,
    ) -> BatchResult:
        """Convenience: process a single observation."""
        return await self.process_batch([observation])
