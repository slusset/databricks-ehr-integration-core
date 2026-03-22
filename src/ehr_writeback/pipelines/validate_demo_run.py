# Databricks notebook source
# MAGIC %md
# MAGIC # Validate Demo Run
# MAGIC
# MAGIC Summarizes the key checks for the issue #6 Databricks validation run and
# MAGIC prints values suitable for screenshots or README evidence.

# COMMAND ----------

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

full_schema = f"{catalog}.{schema}"
queue_table = f"{full_schema}.observations_queue"
log_table = f"{full_schema}.writeback_log"
dead_letters_table = f"{full_schema}.dead_letters"

# COMMAND ----------

queue_df = spark.table(queue_table)  # noqa: F821
log_df = spark.table(log_table)  # noqa: F821
dead_letters_df = spark.table(dead_letters_table)  # noqa: F821

duplicate_keys = (
    log_df.groupBy("idempotency_key").count().where(F.col("count") > 1).count()
)

summary = {
    "queued_observations": queue_df.count(),
    "writeback_log_rows": log_df.count(),
    "dead_letter_rows": dead_letters_df.count(),
    "distinct_idempotency_keys": log_df.select("idempotency_key").distinct().count(),
    "duplicate_idempotency_keys": duplicate_keys,
}

print("Demo validation summary")
for key, value in summary.items():
    print(f"- {key}: {value}")

print("\nStatus counts")
display(log_df.groupBy("status").count().orderBy("status"))  # noqa: F821

print("\nLatest writeback log rows")
display(log_df.orderBy(F.col("attempted_at").desc()).limit(20))  # noqa: F821

print("\nDead-letter rows")
display(dead_letters_df.orderBy(F.col("dead_lettered_at").desc()).limit(20))  # noqa: F821
