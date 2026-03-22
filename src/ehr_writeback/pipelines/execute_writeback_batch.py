# Databricks notebook source
# MAGIC %md
# MAGIC # Execute Writeback Batch
# MAGIC
# MAGIC Reads prepared observations from Delta, writes them to HAPI FHIR through
# MAGIC the orchestrator, and records real outcomes in Delta tables.

# COMMAND ----------

import asyncio
import sys
from pathlib import PurePosixPath

# COMMAND ----------


def _bundle_src_root() -> str:
    notebook_path = (
        dbutils.notebook.entry_point.getDbutils()  # noqa: F821
        .notebook()
        .getContext()
        .notebookPath()
        .get()
    )
    notebook_root = PurePosixPath(notebook_path)
    marker = PurePosixPath("/src/ehr_writeback/pipelines")
    path_str = notebook_root.as_posix()
    prefix, _, _ = path_str.partition(marker.as_posix())
    return f"{prefix}/src"


src_root = _bundle_src_root()
if src_root not in sys.path:
    sys.path.insert(0, src_root)

# COMMAND ----------

from ehr_writeback.adapters.generic.fhir_r4_adapter import GenericFHIRR4Adapter
from ehr_writeback.adapters.generic.no_auth import NoAuth
from ehr_writeback.core.models import (
    EHRSystem,
    Observation,
    WritebackResult,
    WritebackStatus,
)
from ehr_writeback.core.orchestrator import RetryPolicy, WritebackOrchestrator
from ehr_writeback.infrastructure.dead_letter import DeltaDeadLetterStore
from ehr_writeback.infrastructure.delta_store import DeltaStore
from ehr_writeback.infrastructure.idempotency import DeltaIdempotencyStore

# COMMAND ----------

try:
    catalog = dbutils.widgets.get("catalog")  # noqa: F821
except Exception:
    catalog = "ehr_writeback"
try:
    schema = dbutils.widgets.get("schema")  # noqa: F821
except Exception:
    schema = "default"
try:
    fhir_base_url = dbutils.widgets.get("fhir_base_url")  # noqa: F821
except Exception:
    fhir_base_url = "https://hapi.fhir.org/baseR4"
try:
    batch_limit = int(dbutils.widgets.get("batch_limit"))  # noqa: F821
except Exception:
    batch_limit = 100

full_schema = f"{catalog}.{schema}"

# COMMAND ----------

store = DeltaStore(
    spark=spark,  # noqa: F821
    catalog=catalog,
    schema=schema,
)
store.ensure_tables_exist()

idempotency_store = DeltaIdempotencyStore(store=store)
dead_letter_store = DeltaDeadLetterStore(store=store)
adapter = GenericFHIRR4Adapter(base_url=fhir_base_url, auth=NoAuth())

orchestrator = WritebackOrchestrator(
    ehr_adapter=adapter,
    ehr_system=EHRSystem.GENERIC_FHIR,
    idempotency_store=idempotency_store,
    dead_letter_store=dead_letter_store,
    retry_policy=RetryPolicy(
        max_retries=2,
        base_delay_seconds=1.0,
        max_delay_seconds=5.0,
    ),
)

# COMMAND ----------

ready_df = spark.table(f"{full_schema}.writeback_ready").limit(batch_limit)  # noqa: F821
rows = ready_df.collect()

observations = [
    Observation(
        patient_id=row["patient_id"],
        encounter_id=row["encounter_id"],
        code=row["observation_code"],
        code_system=row["code_system"] or "http://loinc.org",
        display_name=row["display_name"] or row["observation_code"],
        value=row["value"],
        unit=row["unit"],
        effective_datetime=row["effective_datetime"].to_pydatetime(),
        source_system=row["source_system"] or "databricks-demo",
    )
    for row in rows
]

print(f"Loaded {len(observations)} observations from {full_schema}.writeback_ready")

# COMMAND ----------


async def _record_dead_letters(result) -> None:
    for dead_letter in result.dead_lettered:
        await idempotency_store.upsert_result(
            WritebackResult(
                observation=dead_letter.observation,
                status=WritebackStatus.DEAD_LETTERED,
                ehr_system=dead_letter.ehr_system,
                idempotency_key=dead_letter.idempotency_key,
                error_message=dead_letter.last_error,
                retry_count=dead_letter.retry_count,
            )
        )


async def _run_batch() -> None:
    connected = await adapter.check_connection()
    if not connected:
        raise RuntimeError(f"Unable to reach FHIR endpoint at {fhir_base_url}")

    result = await orchestrator.process_batch(observations)
    await _record_dead_letters(result)

    print("Writeback batch summary")
    print(f"- succeeded: {len(result.succeeded)}")
    print(f"- skipped: {len(result.skipped)}")
    print(f"- failed: {len(result.failed)}")
    print(f"- dead_lettered: {len(result.dead_lettered)}")


asyncio.run(_run_batch())

# COMMAND ----------

display(spark.table(f"{full_schema}.writeback_log").orderBy("attempted_at"))  # noqa: F821
