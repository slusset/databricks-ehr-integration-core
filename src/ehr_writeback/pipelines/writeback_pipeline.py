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
    name="writeback_log",
    comment="DLT-managed write-back log for staged observations",
)
@dlt.expect_or_drop("valid_patient", "patient_id IS NOT NULL")
@dlt.expect_or_drop("valid_code", "observation_code IS NOT NULL")
def writeback_log():
    """Deduplication and result logging.

    In the full implementation, this table is populated by the
    write-back orchestrator after processing each observation.
    This DLT definition ensures the table schema is managed by DLT
    and participates in the pipeline lineage graph.
    """
    return (
        dlt.read_stream("writeback_staging")
        .withColumn(
            "idempotency_key",
            F.sha2(
                F.concat_ws(
                    ":",
                    F.col("patient_id"),
                    F.col("observation_code"),
                    F.coalesce(
                        F.col("effective_datetime").cast("string"),
                        F.lit(""),
                    ),
                ),
                256,
            ),
        )
        .withColumn("ehr_system", F.lit("generic_fhir"))
        .withColumn("ehr_resource_id", F.lit(None).cast("string"))
        .withColumn("status", F.lit("pending"))
        .withColumn("attempted_at", F.current_timestamp())
        .withColumn("error_message", F.lit(None).cast("string"))
        .withColumn("retry_count", F.lit(0))
        .select(
            "idempotency_key",
            "patient_id",
            F.col("observation_code"),
            "ehr_system",
            "ehr_resource_id",
            "status",
            "attempted_at",
            "error_message",
            "retry_count",
        )
    )


@dlt.table(
    name="dead_letters",
    comment="DLT-managed view of dead-lettered observations",
)
def dead_letters():
    """Expose dead-letter rows through the DLT lineage graph."""
    return (
        dlt.read("writeback_log")
        .where(F.col("status") == F.lit("dead_lettered"))
        .select(
            "idempotency_key",
            "patient_id",
            F.col("observation_code"),
            "ehr_system",
            F.lit(None).cast("string").alias("observation_json"),
            F.coalesce(F.col("error_message"), F.lit("Unknown error")).alias(
                "last_error"
            ),
            "retry_count",
            F.col("attempted_at").alias("dead_lettered_at"),
            F.lit(False).alias("reprocessed"),
        )
    )
