"""Integration tests against HAPI FHIR public R4 server.

Run with:
    FHIR_TEST_BASE_URL=https://hapi.fhir.org/baseR4 uv run pytest tests/integration/ -v

Skipped by default in CI unless FHIR_TEST_BASE_URL is set.
HAPI is a public test server — no auth required, data is ephemeral.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx
import pytest

from ehr_writeback.adapters.generic.fhir_r4_adapter import GenericFHIRR4Adapter
from ehr_writeback.adapters.generic.no_auth import NoAuth
from ehr_writeback.core.models import Observation, WritebackStatus

pytestmark = pytest.mark.skipif(
    not os.environ.get("FHIR_TEST_BASE_URL"),
    reason="Set FHIR_TEST_BASE_URL to run integration tests",
)

FHIR_BASE_URL = os.environ.get("FHIR_TEST_BASE_URL", "")


@pytest.fixture
def adapter() -> GenericFHIRR4Adapter:
    return GenericFHIRR4Adapter(base_url=FHIR_BASE_URL, auth=NoAuth())


@pytest.fixture
async def test_patient_id() -> str:
    """Create a test Patient on HAPI and return its FHIR ID.

    HAPI enforces referential integrity — Observations must reference
    an existing Patient. Uses conditional create (If-None-Exist) to
    avoid 412 on duplicate identifiers.
    """
    patient_resource = {
        "resourceType": "Patient",
        "name": [{"family": "WritebackTest", "given": ["Integration"]}],
        "identifier": [
            {
                "system": "urn:ehr-writeback:integration-test",
                "value": "test-patient-001",
            }
        ],
    }
    async with httpx.AsyncClient() as client:
        # Conditional create: only create if no Patient with this identifier exists
        response = await client.post(
            f"{FHIR_BASE_URL}/Patient",
            json=patient_resource,
            headers={
                "Content-Type": "application/fhir+json",
                "Accept": "application/fhir+json",
                "If-None-Exist": (
                    "identifier=urn:ehr-writeback:integration-test|test-patient-001"
                ),
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

    return data["id"]


@pytest.fixture
def sample_observation(test_patient_id: str) -> Observation:
    return Observation(
        patient_id=test_patient_id,
        code="59408-5",
        code_system="http://loinc.org",
        display_name="Oxygen saturation (SpO2)",
        value=97.5,
        unit="%",
        effective_datetime=datetime.now(timezone.utc),
        source_system="ehr-writeback-integration-test",
        metadata={"test": True},
    )


async def test_check_connection(adapter: GenericFHIRR4Adapter):
    """Verify we can reach the FHIR capability statement."""
    connected = await adapter.check_connection()
    assert connected is True


async def test_write_observation_success(
    adapter: GenericFHIRR4Adapter,
    sample_observation: Observation,
):
    """POST an Observation and verify we get a resource ID back."""
    result = await adapter.write_observation(sample_observation)

    assert result.status == WritebackStatus.SUCCESS, (
        f"Write failed: {result.error_message}"
    )
    assert result.ehr_resource_id is not None
    assert len(result.ehr_resource_id) > 0


async def test_round_trip_observation(
    adapter: GenericFHIRR4Adapter,
    sample_observation: Observation,
):
    """Write an Observation, then GET it back and verify values match."""
    # Write
    result = await adapter.write_observation(sample_observation)
    assert result.status == WritebackStatus.SUCCESS, (
        f"Write failed: {result.error_message}"
    )
    resource_id = result.ehr_resource_id

    # Read back
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{FHIR_BASE_URL}/Observation/{resource_id}",
            headers={"Accept": "application/fhir+json"},
            timeout=30.0,
        )
        assert response.status_code == 200
        data = response.json()

    # Verify
    assert data["resourceType"] == "Observation"
    assert data["status"] == "final"
    assert data["code"]["coding"][0]["code"] == "59408-5"
    assert data["code"]["coding"][0]["system"] == "http://loinc.org"
    assert data["valueQuantity"]["value"] == 97.5
    assert data["valueQuantity"]["unit"] == "%"
    assert sample_observation.patient_id in data["subject"]["reference"]


async def test_write_string_value_observation(
    adapter: GenericFHIRR4Adapter,
    test_patient_id: str,
):
    """Write an observation with a string value (risk level)."""
    obs = Observation(
        patient_id=test_patient_id,
        code="assessment-risk",
        code_system="http://loinc.org",
        display_name="Readmission Risk Level",
        value="moderate",
        effective_datetime=datetime.now(timezone.utc),
    )
    result = await adapter.write_observation(obs)

    assert result.status == WritebackStatus.SUCCESS, (
        f"Write failed: {result.error_message}"
    )
    assert result.ehr_resource_id is not None

    # Read back and verify string value
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{FHIR_BASE_URL}/Observation/{result.ehr_resource_id}",
            headers={"Accept": "application/fhir+json"},
            timeout=30.0,
        )
        data = response.json()

    assert data["valueString"] == "moderate"
