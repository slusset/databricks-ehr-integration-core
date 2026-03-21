# ehr-writeback

[![PyPI version](https://img.shields.io/pypi/v/ehr-writeback.svg)](https://pypi.org/project/ehr-writeback/)

Open-source EHR write-back integration framework. Closes the loop from healthcare analytics back to clinical workflow via FHIR.

## What it does

Analytics platforms (Databricks, Spark, etc.) produce clinical insights — sepsis risk scores, readmission predictions, quality measures. This framework writes those results **back** into EHR systems (Epic, Cerner/Oracle Health, any FHIR R4 server) so clinicians see them in their workflow, not in a separate dashboard.

## Architecture

Hexagonal (ports-and-adapters) design with two deployment targets:

- **Databricks-native** — Delta Live Tables, Lakeflow orchestration, Delta for idempotency
- **Self-hosted** — for orgs not on Databricks or needing fully on-prem

```
┌─────────────────────────────────────────────┐
│              Core Domain                    │
│   models · ports · business rules           │
├──────────────┬──────────────────────────────┤
│  Adapters    │  Infrastructure              │
│  ├─ Epic     │  ├─ IdempotencyStore (Delta) │
│  ├─ Cerner   │  ├─ DeadLetterHandler        │
│  └─ Generic  │  └─ DeltaStore               │
│    FHIR R4   │                              │
└──────────────┴──────────────────────────────┘
```

## Supported EHR Systems

| EHR                  | Status      | Notes                   |
|----------------------|-------------|-------------------------|
| Epic                 | In progress | FHIR R4 + Flowsheet API |
| Cerner/Oracle Health | In progress | FHIR R4 (Millennium)    |
| Generic FHIR R4      | In progress | Any compliant server    |

## Quick Start

Install from PyPI:

```bash
pip install ehr-writeback
```

```bash
uv sync            # install dependencies
uv run pytest      # run unit tests
```

To publish a release, create a GitHub release for a `v*` tag whose version matches `pyproject.toml`. The release workflow builds the wheel and source distribution, publishes through PyPI trusted publishing, and verifies `pip install ehr-writeback==<version>` in a clean environment.

### Run the sepsis risk score example

Generates synthetic patients, scores them for sepsis risk (SIRS + qSOFA),
and writes the results to a public FHIR R4 test server:

```bash
uv run python examples/sepsis_risk_writeback.py
```

Output:
```
[1/4] Generating synthetic patient cohort...
[2/4] Scoring patients for sepsis risk...
  🟢 Barbara Harris: LOW
  🟡 Daniel Moore: MODERATE
  🟠 Charles Harris: HIGH
  🔴 Mary Thompson: CRITICAL
[3/4] Creating Patient resources on FHIR server...
[4/4] Writing sepsis scores to FHIR server...

Results:
  Succeeded:    20
  Success rate: 100%
```

### With Databricks support

```bash
uv sync --extra databricks
```

### Deploy to Databricks

```bash
pip install databricks-cli
databricks bundle deploy -t dev
```

For the end-to-end DLT validation flow, including demo setup and evidence
capture, see the Databricks validation runbook in the docs site.

## Project Structure

```
src/ehr_writeback/
├── core/           # Domain models and port interfaces
├── adapters/       # EHR-specific implementations
│   ├── epic/
│   ├── cerner/
│   └── generic/
├── infrastructure/ # Idempotency, dead-letter, storage
└── pipelines/      # DLT pipeline definitions
```

## License

Apache 2.0 — see [LICENSE](LICENSE).
