"""Synthetic patient data generator for sepsis risk scoring.

Generates clinically realistic vital signs and lab values for
demonstration and testing. Includes a mix of:
- Normal patients (no SIRS criteria met)
- Borderline patients (1-2 SIRS criteria)
- Septic patients (≥2 SIRS criteria + elevated lactate)

Reference ranges and sepsis criteria based on:
- SIRS: Bone et al., Chest 1992
- qSOFA: Singer et al., JAMA 2016
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum


class PatientProfile(str, Enum):
    """Clinical profile for synthetic data generation."""

    NORMAL = "normal"
    BORDERLINE = "borderline"
    SEPTIC = "septic"


@dataclass
class VitalSigns:
    """A single set of vital sign measurements."""

    temperature_c: float  # Celsius
    heart_rate: int  # bpm
    respiratory_rate: int  # breaths/min
    systolic_bp: int  # mmHg
    diastolic_bp: int  # mmHg
    spo2: float  # %

    @property
    def temperature_f(self) -> float:
        return self.temperature_c * 9 / 5 + 32


@dataclass
class LabValues:
    """Relevant lab results for sepsis screening."""

    wbc_count: float  # x10^3/uL
    lactate: float  # mmol/L
    creatinine: float  # mg/dL
    platelet_count: int  # x10^3/uL


@dataclass
class SyntheticPatient:
    """A synthetic patient with vitals and labs."""

    patient_id: str
    name: str
    age: int
    profile: PatientProfile
    vitals: VitalSigns
    labs: LabValues
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(UTC),
    )


# ── Normal ranges ───────────────────────────────────────────

NORMAL_RANGES = {
    "temp_c": (36.1, 37.2),
    "hr": (60, 100),
    "rr": (12, 20),
    "sbp": (100, 140),
    "dbp": (60, 90),
    "spo2": (95.0, 100.0),
    "wbc": (4.5, 11.0),
    "lactate": (0.5, 1.5),
    "creatinine": (0.6, 1.2),
    "platelets": (150, 400),
}

# Septic ranges: designed to trigger SIRS/qSOFA criteria
SEPTIC_RANGES = {
    "temp_c": (38.5, 40.5),  # fever (SIRS: >38°C)
    "hr": (100, 140),  # tachycardia (SIRS: >90)
    "rr": (22, 35),  # tachypnea (SIRS: >20, qSOFA: ≥22)
    "sbp": (70, 95),  # hypotension (qSOFA: ≤100)
    "dbp": (40, 60),
    "spo2": (85.0, 94.0),
    "wbc": (12.0, 25.0),  # leukocytosis (SIRS: >12)
    "lactate": (2.5, 8.0),  # elevated (sepsis marker)
    "creatinine": (1.5, 4.0),  # AKI signal
    "platelets": (50, 140),  # thrombocytopenia
}

FIRST_NAMES = [
    "James",
    "Mary",
    "Robert",
    "Patricia",
    "Michael",
    "Jennifer",
    "David",
    "Linda",
    "William",
    "Barbara",
    "Richard",
    "Susan",
    "Joseph",
    "Jessica",
    "Thomas",
    "Sarah",
    "Charles",
    "Karen",
    "Daniel",
    "Lisa",
]

LAST_NAMES = [
    "Smith",
    "Johnson",
    "Williams",
    "Brown",
    "Jones",
    "Garcia",
    "Miller",
    "Davis",
    "Rodriguez",
    "Martinez",
    "Anderson",
    "Taylor",
    "Thomas",
    "Moore",
    "Jackson",
    "Martin",
    "Lee",
    "Thompson",
    "White",
    "Harris",
]


def _rand(low: float, high: float) -> float:
    return round(random.uniform(low, high), 1)


def _generate_vitals(profile: PatientProfile) -> VitalSigns:
    if profile == PatientProfile.SEPTIC:
        r = SEPTIC_RANGES
    elif profile == PatientProfile.BORDERLINE:
        # Mix: some values normal, some abnormal
        r = {}
        for key in NORMAL_RANGES:
            if random.random() < 0.4:
                r[key] = SEPTIC_RANGES[key]
            else:
                r[key] = NORMAL_RANGES[key]
    else:
        r = NORMAL_RANGES

    return VitalSigns(
        temperature_c=_rand(*r["temp_c"]),
        heart_rate=int(_rand(*r["hr"])),
        respiratory_rate=int(_rand(*r["rr"])),
        systolic_bp=int(_rand(*r["sbp"])),
        diastolic_bp=int(_rand(*r["dbp"])),
        spo2=_rand(*r["spo2"]),
    )


def _generate_labs(profile: PatientProfile) -> LabValues:
    if profile == PatientProfile.SEPTIC:
        r = SEPTIC_RANGES
    elif profile == PatientProfile.BORDERLINE:
        r = {}
        for key in NORMAL_RANGES:
            if random.random() < 0.3:
                r[key] = SEPTIC_RANGES[key]
            else:
                r[key] = NORMAL_RANGES[key]
    else:
        r = NORMAL_RANGES

    return LabValues(
        wbc_count=_rand(*r["wbc"]),
        lactate=_rand(*r["lactate"]),
        creatinine=_rand(*r["creatinine"]),
        platelet_count=int(_rand(*r["platelets"])),
    )


def generate_patient(
    patient_id: str | None = None,
    profile: PatientProfile | None = None,
    timestamp: datetime | None = None,
) -> SyntheticPatient:
    """Generate a single synthetic patient."""
    if profile is None:
        profile = random.choices(
            [PatientProfile.NORMAL, PatientProfile.BORDERLINE, PatientProfile.SEPTIC],
            weights=[0.5, 0.3, 0.2],
        )[0]

    pid = patient_id or f"synth-{random.randint(10000, 99999)}"
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    age = random.randint(25, 90)
    ts = timestamp or datetime.now(UTC) - timedelta(
        minutes=random.randint(0, 480),
    )

    return SyntheticPatient(
        patient_id=pid,
        name=f"{first} {last}",
        age=age,
        profile=profile,
        vitals=_generate_vitals(profile),
        labs=_generate_labs(profile),
        timestamp=ts,
    )


def generate_cohort(
    size: int = 20,
    seed: int | None = 42,
) -> list[SyntheticPatient]:
    """Generate a cohort of synthetic patients.

    Default distribution: 50% normal, 30% borderline, 20% septic.
    Use seed for reproducible results.
    """
    if seed is not None:
        random.seed(seed)

    return [generate_patient() for _ in range(size)]
