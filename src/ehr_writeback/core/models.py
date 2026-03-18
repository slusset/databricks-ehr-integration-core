"""Domain models for EHR write-back operations."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class WritebackStatus(str, Enum):
    """Outcome of a write-back attempt."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    DEAD_LETTERED = "dead_lettered"


class EHRSystem(str, Enum):
    """Supported EHR systems."""

    EPIC = "epic"
    CERNER = "cerner"
    GENERIC_FHIR = "generic_fhir"


class Observation(BaseModel):
    """A clinical observation to write back to the EHR.

    Maps to FHIR R4 Observation resource with fields relevant
    to analytics-derived clinical values (scores, flags, measures).
    """

    patient_id: str = Field(
        description="Patient identifier in the EHR (MRN or FHIR ID)",
    )
    encounter_id: str | None = Field(
        default=None,
        description="Encounter/visit context",
    )
    code: str = Field(
        description="LOINC or local code for the observation type",
    )
    code_system: str = Field(default="http://loinc.org")
    display_name: str = Field(
        description="Human-readable name (e.g. 'Sepsis Risk Score')",
    )
    value: float | str | bool = Field(description="Observation value")
    unit: str | None = Field(default=None, description="UCUM unit if numeric")
    effective_datetime: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_system: str = Field(
        default="ehr-writeback",
        description="Identifier for the analytics system producing this value",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context (model version, confidence, etc.)",
    )


class WritebackResult(BaseModel):
    """Result of a single write-back attempt."""

    observation: Observation
    status: WritebackStatus
    ehr_system: EHRSystem
    ehr_resource_id: str | None = Field(
        default=None, description="ID assigned by the EHR (FHIR resource ID)"
    )
    idempotency_key: str = Field(description="Key used for exactly-once semantics")
    attempted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    error_message: str | None = None
    retry_count: int = 0


class DeadLetter(BaseModel):
    """An observation that exhausted retries and was dead-lettered."""

    observation: Observation
    idempotency_key: str
    ehr_system: EHRSystem
    last_error: str
    retry_count: int
    dead_lettered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reprocessed: bool = False
