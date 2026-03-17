# ehr-writeback

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

```bash
pip install -e ".[dev]"
pytest
```

### With Databricks support

```bash
pip install -e ".[databricks,dev]"
```

### Deploy to Databricks

```bash
pip install databricks-cli
databricks bundle deploy -t dev
```

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
