"""Unit tests for domain models."""

from datetime import datetime

from ehr_writeback.core.models import (
    DeadLetter,
    EHRSystem,
    Observation,
    WritebackResult,
    WritebackStatus,
)


def test_observation_defaults():
    obs = Observation(
        patient_id="P123",
        code="85354-9",
        display_name="Blood pressure panel",
        value=120.0,
        unit="mmHg",
    )
    assert obs.code_system == "http://loinc.org"
    assert obs.source_system == "ehr-writeback"
    assert isinstance(obs.effective_datetime, datetime)
    assert obs.metadata == {}


def test_observation_with_string_value():
    obs = Observation(
        patient_id="P456",
        code="custom-risk",
        display_name="Sepsis Risk",
        value="high",
    )
    assert obs.value == "high"
    assert obs.unit is None


def test_writeback_result_success():
    obs = Observation(
        patient_id="P123",
        code="85354-9",
        display_name="Blood pressure panel",
        value=120.0,
    )
    result = WritebackResult(
        observation=obs,
        status=WritebackStatus.SUCCESS,
        ehr_system=EHRSystem.EPIC,
        ehr_resource_id="fhir-obs-001",
        idempotency_key="abc123",
    )
    assert result.error_message is None
    assert result.retry_count == 0


def test_dead_letter_serialization():
    obs = Observation(
        patient_id="P789",
        code="test-code",
        display_name="Test Observation",
        value=42.0,
    )
    dl = DeadLetter(
        observation=obs,
        idempotency_key="deadkey",
        ehr_system=EHRSystem.CERNER,
        last_error="HTTP 500: Internal Server Error",
        retry_count=3,
    )
    # Round-trip through JSON
    json_str = dl.model_dump_json()
    restored = DeadLetter.model_validate_json(json_str)
    assert restored.idempotency_key == "deadkey"
    assert restored.observation.patient_id == "P789"
