# Databricks notebook source
# MAGIC %md
# MAGIC # Prepare Demo Environment
# MAGIC
# MAGIC Creates the Databricks schema objects needed for the DLT demo and seeds
# MAGIC `observations_queue` with deterministic sample observations.

# COMMAND ----------

from pyspark.sql import Row
from pyspark.sql import functions as F

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
    seed_count = int(dbutils.widgets.get("seed_count"))  # noqa: F821
except Exception:
    seed_count = 10

full_schema = f"{catalog}.{schema}"

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {full_schema}")  # noqa: F821
spark.sql(
    f"""
    CREATE TABLE IF NOT EXISTS {full_schema}.observations_queue (
        patient_id STRING NOT NULL,
        encounter_id STRING,
        observation_code STRING NOT NULL,
        code_system STRING,
        display_name STRING,
        value DOUBLE,
        unit STRING,
        effective_datetime TIMESTAMP,
        source_system STRING
    )
    USING DELTA
    """
)  # noqa: F821

# COMMAND ----------

rows = [
    Row(
        patient_id=f"DEMO-{index:03d}",
        encounter_id=f"ENC-{index:03d}",
        observation_code="8867-4",
        code_system="http://loinc.org",
        display_name="Heart rate",
        value=float(60 + index),
        unit="beats/minute",
        effective_datetime=f"2026-03-21 12:{index:02d}:00",
        source_system="databricks-demo",
    )
    for index in range(seed_count)
]

seed_df = spark.createDataFrame(rows).withColumn(  # noqa: F821
    "effective_datetime", F.to_timestamp("effective_datetime")
)
seed_df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    f"{full_schema}.observations_queue"
)

print(f"Seeded {seed_count} observations into {full_schema}.observations_queue")
display(spark.table(f"{full_schema}.observations_queue").orderBy("patient_id"))  # noqa: F821
