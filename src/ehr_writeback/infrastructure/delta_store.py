"""Delta Lake storage backend.

Provides read/write access to Delta tables for idempotency and dead-letter
storage. Works with both Databricks-managed Spark and local delta-spark.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import SparkSession


@dataclass
class DeltaStore:
    """Thin wrapper around Delta table operations."""

    spark: SparkSession
    catalog: str = "ehr_writeback"
    schema: str = "default"

    def _table_path(self, table_name: str) -> str:
        return f"{self.catalog}.{self.schema}.{table_name}"

    def ensure_tables_exist(self) -> None:
        """Create idempotency and dead-letter tables if they don't exist."""
        self.spark.sql(f"CREATE SCHEMA IF NOT EXISTS {self.catalog}.{self.schema}")

        self.spark.sql(f"""
            CREATE TABLE IF NOT EXISTS {self._table_path("writeback_log")} (
                idempotency_key STRING NOT NULL,
                patient_id STRING,
                observation_code STRING,
                ehr_system STRING,
                ehr_resource_id STRING,
                status STRING,
                attempted_at TIMESTAMP,
                error_message STRING,
                retry_count INT
            )
            USING DELTA
            TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
        """)

        self.spark.sql(f"""
            CREATE TABLE IF NOT EXISTS {self._table_path("dead_letters")} (
                idempotency_key STRING NOT NULL,
                patient_id STRING,
                observation_code STRING,
                ehr_system STRING,
                observation_json STRING,
                last_error STRING,
                retry_count INT,
                dead_lettered_at TIMESTAMP,
                reprocessed BOOLEAN DEFAULT FALSE
            )
            USING DELTA
        """)
