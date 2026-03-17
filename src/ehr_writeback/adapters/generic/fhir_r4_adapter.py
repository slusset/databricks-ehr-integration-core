"""Generic FHIR R4 Observation.Create adapter.

Works with any FHIR R4 compliant server. This is the baseline/fallback
adapter for EHR systems that don't need vendor-specific handling.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import httpx

from ehr_writeback.core.models import (
    EHRSystem,
    Observation,
    WritebackResult,
    WritebackStatus,
)
from ehr_writeback.core.ports import AuthPort, EHRWritebackPort


@dataclass
class GenericFHIRR4Adapter(EHRWritebackPort):
    """Writes observations to any FHIR R4 server via Observation.Create."""

    base_url: str
    auth: AuthPort

    def _build_fhir_observation(self, obs: Observation) -> dict:
        resource: dict = {
            "resourceType": "Observation",
            "status": "final",
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                            "code": "survey",
                            "display": "Survey",
                        }
                    ]
                }
            ],
            "code": {
                "coding": [
                    {
                        "system": obs.code_system,
                        "code": obs.code,
                        "display": obs.display_name,
                    }
                ],
                "text": obs.display_name,
            },
            "subject": {"reference": f"Patient/{obs.patient_id}"},
            "effectiveDateTime": obs.effective_datetime.isoformat(),
        }

        if obs.encounter_id:
            resource["encounter"] = {"reference": f"Encounter/{obs.encounter_id}"}

        if isinstance(obs.value, bool):
            resource["valueBoolean"] = obs.value
        elif isinstance(obs.value, (int, float)):
            resource["valueQuantity"] = {
                "value": obs.value,
                "unit": obs.unit or "",
                "system": "http://unitsofmeasure.org",
            }
        else:
            resource["valueString"] = str(obs.value)

        return resource

    @staticmethod
    def _idempotency_key(obs: Observation) -> str:
        raw = f"fhir:{obs.patient_id}:{obs.code}:{obs.effective_datetime.isoformat()}"
        return hashlib.sha256(raw.encode()).hexdigest()

    async def write_observation(self, observation: Observation) -> WritebackResult:
        token = await self.auth.authenticate()
        fhir_resource = self._build_fhir_observation(observation)
        idem_key = self._idempotency_key(observation)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/Observation",
                    json=fhir_resource,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/fhir+json",
                        "Accept": "application/fhir+json",
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()

                return WritebackResult(
                    observation=observation,
                    status=WritebackStatus.SUCCESS,
                    ehr_system=EHRSystem.GENERIC_FHIR,
                    ehr_resource_id=data.get("id"),
                    idempotency_key=idem_key,
                )
            except httpx.HTTPStatusError as exc:
                return WritebackResult(
                    observation=observation,
                    status=WritebackStatus.FAILED,
                    ehr_system=EHRSystem.GENERIC_FHIR,
                    idempotency_key=idem_key,
                    error_message=(
                        f"HTTP {exc.response.status_code}: {exc.response.text}"
                    ),
                )
            except httpx.RequestError as exc:
                return WritebackResult(
                    observation=observation,
                    status=WritebackStatus.FAILED,
                    ehr_system=EHRSystem.GENERIC_FHIR,
                    idempotency_key=idem_key,
                    error_message=f"Connection error: {exc}",
                )

    async def check_connection(self) -> bool:
        try:
            token = await self.auth.authenticate()
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/metadata",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10.0,
                )
                return response.status_code == 200
        except Exception:
            return False
