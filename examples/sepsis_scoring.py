"""Sepsis risk scoring using SIRS and qSOFA criteria.

Implements two standard clinical scoring systems:

SIRS (Systemic Inflammatory Response Syndrome) — Bone et al., 1992
  ≥2 of the following:
  - Temperature >38°C or <36°C
  - Heart rate >90 bpm
  - Respiratory rate >20 breaths/min
  - WBC >12,000 or <4,000 /µL

qSOFA (Quick Sequential Organ Failure Assessment) — Singer et al., 2016
  ≥2 of the following:
  - Respiratory rate ≥22 breaths/min
  - Altered mentation (not available in this model, excluded)
  - Systolic BP ≤100 mmHg

Combined risk score:
  - LOW:      SIRS < 2 AND qSOFA < 2 AND lactate < 2.0
  - MODERATE: SIRS ≥ 2 OR  qSOFA ≥ 1 OR  lactate ≥ 2.0
  - HIGH:     SIRS ≥ 2 AND (qSOFA ≥ 2 OR lactate ≥ 2.0)
  - CRITICAL: SIRS ≥ 3 AND lactate ≥ 4.0
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from examples.synthetic_patients import LabValues, SyntheticPatient, VitalSigns


class RiskLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SepsisScore:
    """Result of sepsis risk scoring for a patient."""

    patient_id: str
    patient_name: str
    sirs_score: int  # 0-4
    sirs_criteria_met: list[str]
    qsofa_score: int  # 0-2 (without mentation)
    qsofa_criteria_met: list[str]
    lactate: float
    risk_level: RiskLevel
    summary: str


def calculate_sirs(vitals: VitalSigns, labs: LabValues) -> tuple[int, list[str]]:
    """Calculate SIRS score (0-4) and list of met criteria."""
    criteria: list[str] = []

    if vitals.temperature_c > 38.0 or vitals.temperature_c < 36.0:
        criteria.append(
            f"Temperature {vitals.temperature_c}°C "
            f"({'fever' if vitals.temperature_c > 38.0 else 'hypothermia'})"
        )

    if vitals.heart_rate > 90:
        criteria.append(f"Heart rate {vitals.heart_rate} bpm (tachycardia)")

    if vitals.respiratory_rate > 20:
        criteria.append(f"Respiratory rate {vitals.respiratory_rate}/min (tachypnea)")

    if labs.wbc_count > 12.0 or labs.wbc_count < 4.0:
        direction = "leukocytosis" if labs.wbc_count > 12.0 else "leukopenia"
        criteria.append(f"WBC {labs.wbc_count} x10³/µL ({direction})")

    return len(criteria), criteria


def calculate_qsofa(vitals: VitalSigns) -> tuple[int, list[str]]:
    """Calculate qSOFA score (0-2, excluding mentation)."""
    criteria: list[str] = []

    if vitals.respiratory_rate >= 22:
        criteria.append(f"Respiratory rate {vitals.respiratory_rate}/min (≥22)")

    if vitals.systolic_bp <= 100:
        criteria.append(f"Systolic BP {vitals.systolic_bp} mmHg (≤100)")

    return len(criteria), criteria


def score_patient(patient: SyntheticPatient) -> SepsisScore:
    """Score a single patient for sepsis risk."""
    sirs_score, sirs_criteria = calculate_sirs(patient.vitals, patient.labs)
    qsofa_score, qsofa_criteria = calculate_qsofa(patient.vitals)
    lactate = patient.labs.lactate

    # Determine risk level
    if sirs_score >= 3 and lactate >= 4.0:
        risk_level = RiskLevel.CRITICAL
    elif sirs_score >= 2 and (qsofa_score >= 2 or lactate >= 2.0):
        risk_level = RiskLevel.HIGH
    elif sirs_score >= 2 or qsofa_score >= 1 or lactate >= 2.0:
        risk_level = RiskLevel.MODERATE
    else:
        risk_level = RiskLevel.LOW

    # Build summary
    parts = [f"SIRS {sirs_score}/4, qSOFA {qsofa_score}/2"]
    parts.append(f"lactate {lactate} mmol/L")
    if sirs_criteria:
        parts.append(f"SIRS criteria: {', '.join(sirs_criteria)}")
    if qsofa_criteria:
        parts.append(f"qSOFA criteria: {', '.join(qsofa_criteria)}")

    return SepsisScore(
        patient_id=patient.patient_id,
        patient_name=patient.name,
        sirs_score=sirs_score,
        sirs_criteria_met=sirs_criteria,
        qsofa_score=qsofa_score,
        qsofa_criteria_met=qsofa_criteria,
        lactate=lactate,
        risk_level=risk_level,
        summary=" | ".join(parts),
    )


def score_cohort(
    patients: list[SyntheticPatient],
) -> list[SepsisScore]:
    """Score a cohort of patients."""
    return [score_patient(p) for p in patients]
