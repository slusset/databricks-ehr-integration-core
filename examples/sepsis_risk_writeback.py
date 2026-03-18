"""Sepsis risk score write-back — end-to-end example.

Demonstrates the full pipeline:
1. Generate synthetic patient data (vitals + labs)
2. Score patients for sepsis risk (SIRS + qSOFA)
3. Write risk scores back to a FHIR R4 server as Observations
4. Orchestrator handles idempotency, retry, and dead-letter

Usage:
    # Against HAPI FHIR public test server (no auth needed):
    uv run python examples/sepsis_risk_writeback.py

    # Against a custom FHIR server:
    FHIR_BASE_URL=https://your-server/R4 \
        uv run python examples/sepsis_risk_writeback.py
"""

from __future__ import annotations

import asyncio
import os
import sys

import httpx

# Ensure project root is on path for examples/ imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from examples.sepsis_scoring import RiskLevel, SepsisScore, score_cohort
from examples.synthetic_patients import generate_cohort

from ehr_writeback.adapters.generic.fhir_r4_adapter import GenericFHIRR4Adapter
from ehr_writeback.adapters.generic.no_auth import NoAuth

# ── In-memory ports for the example (no Delta/Spark needed) ──
from ehr_writeback.core.models import (
    DeadLetter,
    EHRSystem,
    Observation,
    WritebackResult,
)
from ehr_writeback.core.orchestrator import (
    RetryPolicy,
    WritebackOrchestrator,
)
from ehr_writeback.core.ports import DeadLetterPort, IdempotencyPort


class InMemoryIdempotencyStore(IdempotencyPort):
    def __init__(self) -> None:
        self.processed: dict[str, WritebackResult] = {}

    async def has_been_processed(self, key: str) -> bool:
        return key in self.processed

    async def mark_processed(self, result: WritebackResult) -> None:
        self.processed[result.idempotency_key] = result


class InMemoryDeadLetterStore(DeadLetterPort):
    def __init__(self) -> None:
        self.items: list[DeadLetter] = []

    async def send_to_dead_letter(self, dl: DeadLetter) -> None:
        self.items.append(dl)

    async def get_pending(self, limit: int = 100) -> list[DeadLetter]:
        return [i for i in self.items if not i.reprocessed][:limit]

    async def mark_reprocessed(self, key: str) -> None:
        for i in self.items:
            if i.idempotency_key == key:
                i.reprocessed = True


# ── FHIR code mappings ──────────────────────────────────────

# Using a custom code system for the sepsis risk score since there's
# no standard LOINC code for a computed composite risk level.
SEPSIS_RISK_CODE = "sepsis-risk-score"
SEPSIS_RISK_SYSTEM = "urn:ehr-writeback:sepsis"
SEPSIS_RISK_DISPLAY = "Sepsis Risk Score (SIRS + qSOFA)"

# SIRS score as a separate observation (LOINC doesn't have one,
# but we use a local code)
SIRS_SCORE_CODE = "sirs-score"
SIRS_SCORE_DISPLAY = "SIRS Score"

FHIR_BASE_URL = os.environ.get(
    "FHIR_BASE_URL",
    "https://hapi.fhir.org/baseR4",
)


# ── Patient creation helper ─────────────────────────────────


async def ensure_patients_exist(
    patient_ids: list[str],
    names: list[str],
) -> dict[str, str]:
    """Create FHIR Patient resources and return {synthetic_id: fhir_id}."""
    id_map: dict[str, str] = {}

    async with httpx.AsyncClient() as client:
        for synth_id, name in zip(patient_ids, names, strict=True):
            parts = name.split(" ", 1)
            given = parts[0]
            family = parts[1] if len(parts) > 1 else "Unknown"

            patient_resource = {
                "resourceType": "Patient",
                "name": [{"family": family, "given": [given]}],
                "identifier": [
                    {
                        "system": "urn:ehr-writeback:synthetic",
                        "value": synth_id,
                    }
                ],
            }
            response = await client.post(
                f"{FHIR_BASE_URL}/Patient",
                json=patient_resource,
                headers={
                    "Content-Type": "application/fhir+json",
                    "Accept": "application/fhir+json",
                    "If-None-Exist": (
                        f"identifier=urn:ehr-writeback:synthetic|{synth_id}"
                    ),
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            id_map[synth_id] = data["id"]

    return id_map


# ── Score → Observation conversion ──────────────────────────


def score_to_observations(
    score: SepsisScore,
    fhir_patient_id: str,
    timestamp: str,
) -> list[Observation]:
    """Convert a SepsisScore into FHIR Observations."""
    observations = []

    # 1. Risk level observation (string value)
    observations.append(
        Observation(
            patient_id=fhir_patient_id,
            code=SEPSIS_RISK_CODE,
            code_system=SEPSIS_RISK_SYSTEM,
            display_name=SEPSIS_RISK_DISPLAY,
            value=score.risk_level.value,
            effective_datetime=timestamp,
            source_system="ehr-writeback-example",
            metadata={
                "sirs_score": score.sirs_score,
                "qsofa_score": score.qsofa_score,
                "lactate": score.lactate,
                "summary": score.summary,
            },
        )
    )

    # 2. SIRS score observation (numeric value)
    observations.append(
        Observation(
            patient_id=fhir_patient_id,
            code=SIRS_SCORE_CODE,
            code_system=SEPSIS_RISK_SYSTEM,
            display_name=SIRS_SCORE_DISPLAY,
            value=float(score.sirs_score),
            unit="{score}",
            effective_datetime=timestamp,
            source_system="ehr-writeback-example",
        )
    )

    return observations


# ── Main ────────────────────────────────────────────────────


async def main() -> None:
    print("=" * 70)
    print("Sepsis Risk Score Write-Back Example")
    print(f"FHIR Server: {FHIR_BASE_URL}")
    print("=" * 70)

    # 1. Generate synthetic patients
    print("\n[1/4] Generating synthetic patient cohort...")
    patients = generate_cohort(size=10, seed=42)
    for p in patients:
        print(f"  {p.patient_id}: {p.name} (age {p.age}, profile={p.profile.value})")

    # 2. Score patients
    print("\n[2/4] Scoring patients for sepsis risk...")
    scores = score_cohort(patients)
    risk_counts = {level: 0 for level in RiskLevel}
    for s in scores:
        risk_counts[s.risk_level] += 1
        icon = {
            RiskLevel.LOW: "🟢",
            RiskLevel.MODERATE: "🟡",
            RiskLevel.HIGH: "🟠",
            RiskLevel.CRITICAL: "🔴",
        }[s.risk_level]
        print(f"  {icon} {s.patient_name}: {s.risk_level.value.upper()}")
        print(f"     {s.summary}")

    print(f"\n  Distribution: {dict((k.value, v) for k, v in risk_counts.items())}")

    # 3. Create FHIR Patient resources
    print("\n[3/4] Creating Patient resources on FHIR server...")
    patient_id_map = await ensure_patients_exist(
        patient_ids=[p.patient_id for p in patients],
        names=[p.name for p in patients],
    )
    print(f"  Created/found {len(patient_id_map)} patients")

    # 4. Write scores back via orchestrator
    print("\n[4/4] Writing sepsis scores to FHIR server...")

    adapter = GenericFHIRR4Adapter(
        base_url=FHIR_BASE_URL,
        auth=NoAuth(),
    )
    orchestrator = WritebackOrchestrator(
        ehr_adapter=adapter,
        ehr_system=EHRSystem.GENERIC_FHIR,
        idempotency_store=InMemoryIdempotencyStore(),
        dead_letter_store=InMemoryDeadLetterStore(),
        retry_policy=RetryPolicy(
            max_retries=2,
            base_delay_seconds=1.0,
        ),
    )

    # Build all observations
    all_observations: list[Observation] = []
    for patient, score in zip(patients, scores, strict=True):
        fhir_id = patient_id_map[patient.patient_id]
        obs_list = score_to_observations(
            score,
            fhir_patient_id=fhir_id,
            timestamp=patient.timestamp,
        )
        all_observations.extend(obs_list)

    print(f"  Submitting {len(all_observations)} observations...")
    result = await orchestrator.process_batch(all_observations)

    # 5. Report results
    print("\n" + "=" * 70)
    print("Results:")
    print(f"  Succeeded:    {len(result.succeeded)}")
    print(f"  Skipped:      {len(result.skipped)}")
    print(f"  Failed:       {len(result.failed)}")
    print(f"  Dead-lettered: {len(result.dead_lettered)}")
    print(f"  Success rate: {result.success_rate:.0%}")

    if result.succeeded:
        print("\n  FHIR resource IDs written:")
        for wb in result.succeeded[:5]:
            print(f"    {wb.ehr_resource_id} ({wb.observation.display_name})")
        if len(result.succeeded) > 5:
            print(f"    ... and {len(result.succeeded) - 5} more")

    print("\n" + "=" * 70)
    print(
        f"View results: {FHIR_BASE_URL}/Observation"
        f"?code={SEPSIS_RISK_CODE}&_sort=-date&_count=20"
    )
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
