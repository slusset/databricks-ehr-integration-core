"""Epic Flowsheet (ADDFLOWSHEETVALUE) adapter.

This is Epic's proprietary (non-FHIR) API for writing values into
flowsheet rows. Used when the target is a nursing flowsheet rather
than a FHIR Observation resource.

See: Epic's Interconnect ADDFLOWSHEETVALUE web service documentation.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import httpx

from ehr_writeback.adapters.epic.auth import EpicBackendJWTAuth
from ehr_writeback.core.models import (
    EHRSystem,
    Observation,
    WritebackResult,
    WritebackStatus,
)
from ehr_writeback.core.ports import EHRWritebackPort


@dataclass
class EpicFlowsheetAdapter(EHRWritebackPort):
    """Writes observations to Epic flowsheets via ADDFLOWSHEETVALUE."""

    base_url: str  # Interconnect base URL
    auth: EpicBackendJWTAuth

    def _build_flowsheet_payload(self, obs: Observation) -> dict:
        """Convert domain Observation to Epic flowsheet payload."""
        return {
            "PatientID": obs.patient_id,
            "PatientIDType": "FHIR",
            "ContactID": obs.encounter_id or "",
            "ContactIDType": "CSN",
            "FlowsheetRowID": obs.code,
            "FlowsheetRowIDType": "EXTERNAL",
            "Value": str(obs.value),
            "InstantValueTaken": obs.effective_datetime.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "FlowsheetTemplateID": obs.metadata.get("flowsheet_template_id", ""),
        }

    @staticmethod
    def _idempotency_key(obs: Observation) -> str:
        raw = f"fs:{obs.patient_id}:{obs.code}:{obs.effective_datetime.isoformat()}"
        return hashlib.sha256(raw.encode()).hexdigest()

    async def write_observation(self, observation: Observation) -> WritebackResult:
        token = await self.auth.get_token()
        payload = self._build_flowsheet_payload(observation)
        idem_key = self._idempotency_key(observation)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/epic/2014/Clinical/Patient/ADDFLOWSHEETVALUE/FlowsheetValue",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    timeout=30.0,
                )
                response.raise_for_status()

                return WritebackResult(
                    observation=observation,
                    status=WritebackStatus.SUCCESS,
                    ehr_system=EHRSystem.EPIC,
                    idempotency_key=idem_key,
                )
            except httpx.HTTPStatusError as exc:
                return WritebackResult(
                    observation=observation,
                    status=WritebackStatus.FAILED,
                    ehr_system=EHRSystem.EPIC,
                    idempotency_key=idem_key,
                    error_message=(
                        f"HTTP {exc.response.status_code}: {exc.response.text}"
                    ),
                )
            except httpx.RequestError as exc:
                return WritebackResult(
                    observation=observation,
                    status=WritebackStatus.FAILED,
                    ehr_system=EHRSystem.EPIC,
                    idempotency_key=idem_key,
                    error_message=f"Connection error: {exc}",
                )

    async def check_connection(self) -> bool:
        try:
            token = await self.auth.get_token()
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/FHIR/R4/metadata",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10.0,
                )
                return response.status_code == 200
        except Exception:
            return False
