"""Unit tests for the write-back orchestrator.

Uses in-memory mock implementations of all ports so we can test
the orchestration logic (idempotency, retry, dead-letter, circuit
breaker) without any external dependencies.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ehr_writeback.core.models import (
    DeadLetter,
    EHRSystem,
    Observation,
    WritebackResult,
    WritebackStatus,
)
from ehr_writeback.core.orchestrator import (
    BatchResult,
    CircuitBreaker,
    CircuitState,
    RetryPolicy,
    WritebackOrchestrator,
)
from ehr_writeback.core.ports import (
    DeadLetterPort,
    EHRWritebackPort,
    IdempotencyPort,
)


# ── In-memory port implementations for testing ─────────────


class InMemoryIdempotencyStore(IdempotencyPort):
    def __init__(self) -> None:
        self.processed: dict[str, WritebackResult] = {}

    async def has_been_processed(self, idempotency_key: str) -> bool:
        return idempotency_key in self.processed

    async def mark_processed(self, result: WritebackResult) -> None:
        self.processed[result.idempotency_key] = result


class InMemoryDeadLetterStore(DeadLetterPort):
    def __init__(self) -> None:
        self.items: list[DeadLetter] = []

    async def send_to_dead_letter(self, dead_letter: DeadLetter) -> None:
        self.items.append(dead_letter)

    async def get_pending(self, limit: int = 100) -> list[DeadLetter]:
        return [dl for dl in self.items if not dl.reprocessed][:limit]

    async def mark_reprocessed(self, idempotency_key: str) -> None:
        for dl in self.items:
            if dl.idempotency_key == idempotency_key:
                dl.reprocessed = True


class MockEHRAdapter(EHRWritebackPort):
    """Configurable mock: can succeed, fail N times then succeed, or always fail."""

    def __init__(
        self,
        *,
        fail_count: int = 0,
        always_fail: bool = False,
    ) -> None:
        self.fail_count = fail_count
        self.always_fail = always_fail
        self._call_count: dict[str, int] = {}
        self.written: list[Observation] = []

    async def write_observation(self, observation: Observation) -> WritebackResult:
        key = observation.patient_id
        self._call_count[key] = self._call_count.get(key, 0) + 1
        calls = self._call_count[key]

        if self.always_fail or calls <= self.fail_count:
            return WritebackResult(
                observation=observation,
                status=WritebackStatus.FAILED,
                ehr_system=EHRSystem.GENERIC_FHIR,
                idempotency_key="",
                error_message=f"Simulated failure #{calls}",
            )

        self.written.append(observation)
        return WritebackResult(
            observation=observation,
            status=WritebackStatus.SUCCESS,
            ehr_system=EHRSystem.GENERIC_FHIR,
            ehr_resource_id=f"fhir-{observation.patient_id}",
            idempotency_key="",
        )

    async def check_connection(self) -> bool:
        return not self.always_fail


# ── Fixtures ────────────────────────────────────────────────


def _make_observation(
    patient_id: str = "P100",
    code: str = "59408-5",
) -> Observation:
    return Observation(
        patient_id=patient_id,
        code=code,
        display_name="Test Observation",
        value=42.0,
        unit="%",
        effective_datetime=datetime(2025, 6, 15, 10, 30, tzinfo=timezone.utc),
    )


def _make_orchestrator(
    adapter: MockEHRAdapter | None = None,
    idem_store: InMemoryIdempotencyStore | None = None,
    dl_store: InMemoryDeadLetterStore | None = None,
    retry_policy: RetryPolicy | None = None,
    circuit_breaker: CircuitBreaker | None = None,
) -> tuple[
    WritebackOrchestrator,
    MockEHRAdapter,
    InMemoryIdempotencyStore,
    InMemoryDeadLetterStore,
]:
    a = adapter or MockEHRAdapter()
    i = idem_store or InMemoryIdempotencyStore()
    d = dl_store or InMemoryDeadLetterStore()
    orch = WritebackOrchestrator(
        ehr_adapter=a,
        ehr_system=EHRSystem.GENERIC_FHIR,
        idempotency_store=i,
        dead_letter_store=d,
        retry_policy=retry_policy
        or RetryPolicy(
            max_retries=3,
            base_delay_seconds=0.01,
            max_delay_seconds=0.05,
        ),
        circuit_breaker=circuit_breaker
        or CircuitBreaker(
            failure_threshold=10,
            recovery_timeout_seconds=0.1,
        ),
    )
    return orch, a, i, d


# ── Tests ───────────────────────────────────────────────────


async def test_happy_path_single_observation():
    """Single observation writes successfully on first attempt."""
    orch, adapter, idem, dl = _make_orchestrator()
    obs = _make_observation()

    result = await orch.process_single(obs)

    assert len(result.succeeded) == 1
    assert len(result.skipped) == 0
    assert len(result.dead_lettered) == 0
    assert result.succeeded[0].ehr_resource_id == "fhir-P100"
    assert len(adapter.written) == 1
    assert len(idem.processed) == 1


async def test_happy_path_batch():
    """Multiple observations all succeed."""
    orch, adapter, idem, dl = _make_orchestrator()
    observations = [
        _make_observation(patient_id=f"P{i}", code=f"code-{i}") for i in range(5)
    ]

    result = await orch.process_batch(observations)

    assert len(result.succeeded) == 5
    assert result.success_rate == 1.0
    assert len(adapter.written) == 5


async def test_idempotency_skip():
    """Already-processed observation is skipped."""
    orch, adapter, idem, dl = _make_orchestrator()
    obs = _make_observation()

    # Process once
    result1 = await orch.process_single(obs)
    assert len(result1.succeeded) == 1

    # Process again — should be skipped
    result2 = await orch.process_single(obs)
    assert len(result2.skipped) == 1
    assert len(result2.succeeded) == 0
    # Adapter should only have been called once total
    assert len(adapter.written) == 1


async def test_retry_then_succeed():
    """Observation fails twice then succeeds on third attempt."""
    adapter = MockEHRAdapter(fail_count=2)
    orch, adapter, idem, dl = _make_orchestrator(adapter=adapter)
    obs = _make_observation()

    result = await orch.process_single(obs)

    assert len(result.succeeded) == 1
    assert result.succeeded[0].retry_count == 2
    assert len(result.dead_lettered) == 0
    assert len(adapter.written) == 1


async def test_exhaust_retries_dead_letter():
    """Observation fails all attempts and gets dead-lettered."""
    adapter = MockEHRAdapter(always_fail=True)
    orch, adapter, idem, dl = _make_orchestrator(adapter=adapter)
    obs = _make_observation()

    result = await orch.process_single(obs)

    assert len(result.succeeded) == 0
    assert len(result.dead_lettered) == 1
    assert result.dead_lettered[0].retry_count == 3
    assert "Simulated failure" in result.dead_lettered[0].last_error
    assert len(dl.items) == 1
    assert len(idem.processed) == 0


async def test_circuit_breaker_opens():
    """Circuit breaker opens after threshold failures."""
    adapter = MockEHRAdapter(always_fail=True)
    cb = CircuitBreaker(
        failure_threshold=3,
        recovery_timeout_seconds=60.0,
    )
    orch, adapter, idem, dl = _make_orchestrator(
        adapter=adapter,
        circuit_breaker=cb,
        retry_policy=RetryPolicy(
            max_retries=1,
            base_delay_seconds=0.01,
        ),
    )

    # Process enough to trip the breaker
    obs1 = _make_observation(patient_id="P1", code="c1")
    await orch.process_single(obs1)

    # After the first observation exhausts retries (2 failures),
    # process another to push past threshold
    obs2 = _make_observation(patient_id="P2", code="c2")
    await orch.process_single(obs2)

    # Circuit should now be open
    assert cb.state == CircuitState.OPEN

    # Next observation should be immediately dead-lettered
    obs3 = _make_observation(patient_id="P3", code="c3")
    result3 = await orch.process_single(obs3)
    assert len(result3.dead_lettered) == 1
    assert "Circuit breaker open" in result3.dead_lettered[0].last_error


async def test_mixed_batch():
    """Batch with a mix of new and already-processed observations."""
    orch, adapter, idem, dl = _make_orchestrator()

    obs_first = _make_observation(patient_id="P1", code="c1")
    await orch.process_single(obs_first)

    # Now batch: P1 (already done) + P2 (new) + P3 (new)
    batch = [
        _make_observation(patient_id="P1", code="c1"),
        _make_observation(patient_id="P2", code="c2"),
        _make_observation(patient_id="P3", code="c3"),
    ]
    result = await orch.process_batch(batch)

    assert len(result.skipped) == 1
    assert len(result.succeeded) == 2
    assert result.total == 3


async def test_retry_policy_backoff():
    """Verify exponential backoff calculation."""
    policy = RetryPolicy(
        base_delay_seconds=1.0,
        max_delay_seconds=30.0,
        exponential_base=2.0,
    )
    assert policy.delay_for_attempt(0) == 1.0
    assert policy.delay_for_attempt(1) == 2.0
    assert policy.delay_for_attempt(2) == 4.0
    assert policy.delay_for_attempt(3) == 8.0
    # Capped at max
    assert policy.delay_for_attempt(10) == 30.0


async def test_batch_result_metrics():
    """BatchResult correctly computes totals and rates."""
    r = BatchResult()
    assert r.total == 0
    assert r.success_rate == 0.0

    obs = _make_observation()
    r.succeeded.append(
        WritebackResult(
            observation=obs,
            status=WritebackStatus.SUCCESS,
            ehr_system=EHRSystem.GENERIC_FHIR,
            idempotency_key="k1",
        )
    )
    r.skipped.append("k2")
    assert r.total == 2
    assert r.success_rate == 0.5
