"""Delta-backed idempotency store.

Uses Delta MERGE for exactly-once write semantics. Before writing an
observation to the EHR, the pipeline checks this store. If the key
exists with status=SUCCESS, the write is skipped.
"""

from __future__ import annotations

from dataclasses import dataclass

from ehr_writeback.core.models import WritebackResult
from ehr_writeback.core.ports import IdempotencyPort
from ehr_writeback.infrastructure.delta_store import DeltaStore


@dataclass
class DeltaIdempotencyStore(IdempotencyPort):
    """Idempotency backed by a Delta table with MERGE upsert."""

    store: DeltaStore
    table_name: str = "writeback_log"

    @property
    def _table(self) -> str:
        return self.store._table_path(self.table_name)

    async def has_been_processed(self, idempotency_key: str) -> bool:
        df = self.store.spark.sql(
            f"SELECT 1 FROM {self._table} "
            f"WHERE idempotency_key = '{idempotency_key}' AND status = 'success' "
            f"LIMIT 1"
        )
        return df.count() > 0

    async def mark_processed(self, result: WritebackResult) -> None:
        row = self.store.spark.createDataFrame(
            [
                {
                    "idempotency_key": result.idempotency_key,
                    "patient_id": result.observation.patient_id,
                    "observation_code": result.observation.code,
                    "ehr_system": result.ehr_system.value,
                    "ehr_resource_id": result.ehr_resource_id,
                    "status": result.status.value,
                    "attempted_at": result.attempted_at,
                    "error_message": result.error_message,
                    "retry_count": result.retry_count,
                }
            ]
        )

        from delta.tables import DeltaTable

        target = DeltaTable.forName(self.store.spark, self._table)
        (
            target.alias("t")
            .merge(row.alias("s"), "t.idempotency_key = s.idempotency_key")
            .whenMatchedUpdateAll()
            .whenNotMatchedInsertAll()
            .execute()
        )
