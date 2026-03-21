# Architecture

The repository follows a hexagonal architecture:

- `src/ehr_writeback/core/` contains the domain models, ports, and orchestration logic
- `src/ehr_writeback/adapters/` contains EHR-specific adapter implementations
- `src/ehr_writeback/infrastructure/` contains persistence and dead-letter support
- `src/ehr_writeback/pipelines/` contains Databricks-oriented pipeline code

## Design intent

The core orchestrator coordinates:

- idempotency checks before write-back
- retry behavior for transient failures
- circuit breaker behavior for unhealthy endpoints
- dead-letter handling after retry exhaustion

Adapters are responsible for translating the core model into each EHR's API
shape without leaking adapter-specific behavior back into the domain layer.
