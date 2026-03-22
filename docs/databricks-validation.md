# Databricks Validation

This runbook captures the repo-side steps for issue `#6`:

- deploy the Databricks Asset Bundle
- seed at least 10 observations into the staging table
- run the DLT pipeline
- confirm Delta outputs and idempotency behavior
- capture evidence for docs or the README

## Prerequisites

- Databricks workspace access
- Databricks CLI authenticated against the target workspace
- Access to a reachable HAPI FHIR endpoint if full external write-back is being validated

## Deploy the bundle

Choose a catalog you can write to first. On Databricks Free Edition, that is
often your workspace catalog rather than a custom catalog name.

```bash
databricks bundle validate -t dev --var="catalog=<your_catalog>"
databricks bundle deploy -t dev --var="catalog=<your_catalog>"
```

If `catalog` is omitted, bundle validation should fail fast instead of trying to
deploy into a catalog that does not exist in your workspace.

## Seed demo data

Run the `ehr-writeback-demo-setup` job after deployment. It creates or refreshes:

- `${catalog}.${schema}.observations_queue`

and seeds 10 deterministic observations for pipeline validation.

## Execute the writeback path

Run the `ehr-writeback-batch` job. It:

1. refreshes the DLT staging pipeline
2. executes the writeback notebook against the configured FHIR endpoint

Expected Delta outputs:

- `${catalog}.${schema}.writeback_ready`
- `${catalog}.${schema}.writeback_log`
- `${catalog}.${schema}.dead_letters`

## Validate the run

Run the `ehr-writeback-demo-validation` job. It reports:

- queued observation count
- write-back log row count
- dead-letter row count
- distinct versus duplicate idempotency keys
- status breakdown from `writeback_log`

For the issue acceptance criteria, capture screenshots of:

1. successful `databricks bundle deploy -t dev`
2. the DLT pipeline run summary
3. `writeback_log` row counts after the first run
4. unchanged distinct idempotency key count after a rerun
5. dead-letter reprocess output, if dead letters are present

## Current limitation

The repo now contains the bundle jobs, validation notebooks, and docs runbook
needed to execute the demo in a Databricks workspace. Final issue completion
still requires an actual workspace run and the associated evidence capture.
