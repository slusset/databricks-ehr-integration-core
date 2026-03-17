# Databricks notebook source
# MAGIC %md
# MAGIC # EHR Write-Back Pipeline (DLT)
# MAGIC
# MAGIC Reads analytics output from a staging table, deduplicates via the
# MAGIC idempotency store, writes to the configured EHR, and logs results.

# COMMAND ----------

import dlt
from pyspark.sql import functions as F

# COMMAND ----------

# Configuration from pipeline settings
catalog = spark.conf.get("ehr_writeback.catalog", "ehr_writeback")
schema = spark.conf.get("ehr_writeback.schema", "default")

# COMMAND ----------


@dlt.table(
    name="writeback_staging",
    comment="Analytics observations staged for EHR write-back",
)
def writeback_staging():
    """Read observations queued by upstream analytics pipelines."""
    return spark.readStream.table(f"{catalog}.{schema}.observations_queue")


# COMMAND ----------


@dlt.table(
    name="writeback_results",
    comment="Results of EHR write-back attempts",
)
@dlt.expect_or_drop("valid_patient", "patient_id IS NOT NULL")
@dlt.expect_or_drop("valid_code", "observation_code IS NOT NULL")
def writeback_results():
    """Deduplication and result logging.

    In the full implementation, this table is populated by the
    write-back orchestrator after processing each observation.
    This DLT definition ensures the table schema is managed by DLT
    and participates in the pipeline lineage graph.
    """
    return (
        dlt.read_stream("writeback_staging")
        .withColumn("processed_at", F.current_timestamp())
        .withColumn("status", F.lit("pending"))
    )
