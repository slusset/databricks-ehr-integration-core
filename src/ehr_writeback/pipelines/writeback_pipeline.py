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
    name="writeback_ready",
    comment="Validated observations ready for the writeback job",
)
@dlt.expect_or_drop("valid_patient", "patient_id IS NOT NULL")
@dlt.expect_or_drop("valid_code", "observation_code IS NOT NULL")
def writeback_ready():
    """Prepare observations for the side-effecting writeback notebook job."""
    return (
        dlt.read_stream("writeback_staging")
        .withColumn("queued_at", F.current_timestamp())
        .select(
            "patient_id",
            "encounter_id",
            F.col("observation_code"),
            "code_system",
            "display_name",
            "value",
            "unit",
            "effective_datetime",
            "source_system",
            "queued_at",
        )
    )
