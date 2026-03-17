"""Port interfaces (hexagonal architecture boundaries).

These ABCs define what the core domain *needs* from the outside world.
Adapters implement these ports for specific EHR systems and storage backends.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ehr_writeback.core.models import (
    DeadLetter,
    Observation,
    WritebackResult,
)


class EHRWritebackPort(ABC):
    """Port for writing observations back to an EHR system."""

    @abstractmethod
    async def write_observation(self, observation: Observation) -> WritebackResult:
        """Write a single observation to the EHR.

        Implementations handle FHIR resource creation, flowsheet writes, etc.
        """

    @abstractmethod
    async def check_connection(self) -> bool:
        """Verify connectivity to the EHR endpoint."""


class AuthPort(ABC):
    """Port for EHR authentication."""

    @abstractmethod
    async def authenticate(self) -> str:
        """Obtain a valid access token. Returns the token string."""

    @abstractmethod
    async def refresh(self) -> str:
        """Refresh an expired token. Returns the new token string."""


class IdempotencyPort(ABC):
    """Port for exactly-once write semantics."""

    @abstractmethod
    async def has_been_processed(self, idempotency_key: str) -> bool:
        """Check whether this key has already been successfully processed."""

    @abstractmethod
    async def mark_processed(self, result: WritebackResult) -> None:
        """Record a successful write-back for deduplication."""


class DeadLetterPort(ABC):
    """Port for dead-letter handling of failed write-backs."""

    @abstractmethod
    async def send_to_dead_letter(self, dead_letter: DeadLetter) -> None:
        """Persist a failed observation for later reprocessing."""

    @abstractmethod
    async def get_pending(self, limit: int = 100) -> list[DeadLetter]:
        """Retrieve dead-lettered observations eligible for reprocessing."""

    @abstractmethod
    async def mark_reprocessed(self, idempotency_key: str) -> None:
        """Mark a dead-lettered observation as successfully reprocessed."""
