# Databricks notebook source
# MAGIC %md
# MAGIC # Reprocess Dead-Lettered Observations
# MAGIC
# MAGIC Scheduled job that picks up failed observations from the dead-letter
# MAGIC table and retries them against the configured EHR adapter.

# COMMAND ----------

# MAGIC %pip install ehr-writeback

# COMMAND ----------

dbutils.library.restartPython()  # noqa: F821 — Databricks provides dbutils

# COMMAND ----------

from ehr_writeback.infrastructure.dead_letter import DeltaDeadLetterStore
from ehr_writeback.infrastructure.delta_store import DeltaStore

try:
    catalog = dbutils.widgets.get("catalog")  # noqa: F821
except Exception:
    catalog = "ehr_writeback"
try:
    schema = dbutils.widgets.get("schema")  # noqa: F821
except Exception:
    schema = "default"

store = DeltaStore(
    spark=spark,
    catalog=catalog,
    schema=schema,  # noqa: F821
)
dead_letter_store = DeltaDeadLetterStore(store=store)

# COMMAND ----------

import asyncio


async def reprocess():
    pending = await dead_letter_store.get_pending(limit=500)
    print(f"Found {len(pending)} dead-lettered observations to reprocess")

    # TODO: Initialize the appropriate EHR adapter based on dead_letter.ehr_system
    # and retry each observation. On success, mark_reprocessed.
    for dl in pending:
        print(
            f"  - {dl.idempotency_key}: {dl.observation.display_name} ({dl.last_error})"
        )


asyncio.run(reprocess())
