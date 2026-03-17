"""Tests for FHIR resource construction across adapters."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

from ehr_writeback.adapters.epic.fhir_adapter import EpicFHIRAdapter
from ehr_writeback.adapters.cerner.fhir_adapter import CernerFHIRAdapter
from ehr_writeback.adapters.generic.fhir_r4_adapter import GenericFHIRR4Adapter
from ehr_writeback.core.models import Observation


def _sample_observation() -> Observation:
    return Observation(
        patient_id="P100",
        encounter_id="E200",
        code="59408-5",
        display_name="Oxygen saturation",
        value=98.5,
        unit="%",
        effective_datetime=datetime(2025, 6, 15, 10, 30, 0, tzinfo=timezone.utc),
    )


def test_epic_fhir_resource_structure():
    mock_auth = AsyncMock()
    adapter = EpicFHIRAdapter(base_url="https://example.com/fhir/R4", auth=mock_auth)
    obs = _sample_observation()
    resource = adapter._build_fhir_observation(obs)

    assert resource["resourceType"] == "Observation"
    assert resource["status"] == "final"
    assert resource["subject"]["reference"] == "Patient/P100"
    assert resource["encounter"]["reference"] == "Encounter/E200"
    assert resource["valueQuantity"]["value"] == 98.5
    assert resource["valueQuantity"]["unit"] == "%"
    assert resource["code"]["coding"][0]["code"] == "59408-5"


def test_cerner_fhir_resource_structure():
    mock_auth = AsyncMock()
    adapter = CernerFHIRAdapter(base_url="https://example.com/fhir/R4", auth=mock_auth)
    obs = _sample_observation()
    resource = adapter._build_fhir_observation(obs)

    assert resource["resourceType"] == "Observation"
    assert resource["subject"]["reference"] == "Patient/P100"


def test_generic_fhir_resource_with_boolean():
    mock_auth = AsyncMock()
    adapter = GenericFHIRR4Adapter(base_url="https://example.com/fhir/R4", auth=mock_auth)
    obs = Observation(
        patient_id="P300",
        code="sepsis-flag",
        display_name="Sepsis Alert",
        value=True,
    )
    resource = adapter._build_fhir_observation(obs)

    assert resource["valueBoolean"] is True
    assert "valueQuantity" not in resource
    assert "valueString" not in resource


def test_generic_fhir_resource_with_string():
    mock_auth = AsyncMock()
    adapter = GenericFHIRR4Adapter(base_url="https://example.com/fhir/R4", auth=mock_auth)
    obs = Observation(
        patient_id="P400",
        code="risk-level",
        display_name="Readmission Risk",
        value="moderate",
    )
    resource = adapter._build_fhir_observation(obs)

    assert resource["valueString"] == "moderate"


def test_idempotency_keys_differ_across_adapters():
    """Same observation should produce different keys per adapter to avoid collisions."""
    obs = _sample_observation()
    epic_key = EpicFHIRAdapter._idempotency_key(obs)
    cerner_key = CernerFHIRAdapter._idempotency_key(obs)
    generic_key = GenericFHIRR4Adapter._idempotency_key(obs)

    assert epic_key != cerner_key
    assert cerner_key != generic_key
