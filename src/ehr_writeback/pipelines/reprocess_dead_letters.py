# Databricks notebook source
# MAGIC %md
# MAGIC # Reprocess Dead-Lettered Observations
# MAGIC
# MAGIC Scheduled job that picks up failed observations from the dead-letter
# MAGIC table and retries them against the configured EHR adapter.

# COMMAND ----------

import asyncio
import sys
from pathlib import PurePosixPath


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
from ehr_writeback.core.models import EHRSystem
from ehr_writeback.core.orchestrator import RetryPolicy, WritebackOrchestrator
from ehr_writeback.infrastructure.dead_letter import DeltaDeadLetterStore
from ehr_writeback.infrastructure.delta_store import DeltaStore
from ehr_writeback.infrastructure.idempotency import DeltaIdempotencyStore

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

store = DeltaStore(
    spark=spark,
    catalog=catalog,
    schema=schema,  # noqa: F821
)
dead_letter_store = DeltaDeadLetterStore(store=store)
idempotency_store = DeltaIdempotencyStore(store=store)
adapter = GenericFHIRR4Adapter(base_url=fhir_base_url, auth=NoAuth())
orchestrator = WritebackOrchestrator(
    ehr_adapter=adapter,
    ehr_system=EHRSystem.GENERIC_FHIR,
    idempotency_store=idempotency_store,
    dead_letter_store=dead_letter_store,
    retry_policy=RetryPolicy(
        max_retries=1,
        base_delay_seconds=1.0,
        max_delay_seconds=5.0,
    ),
)

# COMMAND ----------


async def reprocess() -> None:
    pending = await dead_letter_store.get_pending(limit=500)
    print(f"Found {len(pending)} dead-lettered observations to reprocess")

    for dl in pending:
        result = await orchestrator.process_single(dl.observation)
        if result.succeeded:
            await dead_letter_store.mark_reprocessed(dl.idempotency_key)
            print(f"Reprocessed {dl.idempotency_key} successfully")
        else:
            print(f"Still failing: {dl.idempotency_key}")


asyncio.run(reprocess())
