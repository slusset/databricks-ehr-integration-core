# ehr-writeback

`ehr-writeback` closes the loop from analytics outputs back into clinical
workflow by writing observations into EHR systems through FHIR.

## What it covers

- Core write-back orchestration with idempotency, retries, and dead-lettering
- Adapters for Epic, Cerner/Oracle Health, and generic FHIR R4 endpoints
- Databricks-oriented pipeline support for operational deployments

## Project goals

- Keep business logic in the core domain layer
- Isolate EHR-specific behavior inside adapters
- Support production-safe write-back patterns such as retries and exactly-once semantics

## Contributing

See `CONTRIBUTING.md` for development setup, pull request expectations, and the
local verification commands used in CI.
