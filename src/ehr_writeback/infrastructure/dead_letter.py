"""Delta-backed dead-letter queue.

Observations that exhaust retries are written here for manual review
or scheduled reprocessing.
"""

from __future__ import annotations

from dataclasses import dataclass

from ehr_writeback.core.models import DeadLetter
from ehr_writeback.core.ports import DeadLetterPort
from ehr_writeback.infrastructure.delta_store import DeltaStore


@dataclass
class DeltaDeadLetterStore(DeadLetterPort):
    """Dead-letter queue backed by a Delta table."""

    store: DeltaStore
    table_name: str = "dead_letters"

    @property
    def _table(self) -> str:
        return self.store._table_path(self.table_name)

    async def send_to_dead_letter(self, dead_letter: DeadLetter) -> None:
        row = self.store.spark.createDataFrame(
            [
                {
                    "idempotency_key": dead_letter.idempotency_key,
                    "patient_id": dead_letter.observation.patient_id,
                    "observation_code": dead_letter.observation.code,
                    "ehr_system": dead_letter.ehr_system.value,
                    "observation_json": dead_letter.observation.model_dump_json(),
                    "last_error": dead_letter.last_error,
                    "retry_count": dead_letter.retry_count,
                    "dead_lettered_at": dead_letter.dead_lettered_at,
                    "reprocessed": False,
                }
            ]
        )
        row.write.mode("append").saveAsTable(self._table)

    async def get_pending(self, limit: int = 100) -> list[DeadLetter]:
        from ehr_writeback.core.models import EHRSystem, Observation

        df = self.store.spark.sql(
            f"SELECT * FROM {self._table} "
            f"WHERE reprocessed = FALSE "
            f"ORDER BY dead_lettered_at ASC "
            f"LIMIT {limit}"
        )
        results = []
        for row in df.collect():
            obs = Observation.model_validate_json(row["observation_json"])
            results.append(
                DeadLetter(
                    observation=obs,
                    idempotency_key=row["idempotency_key"],
                    ehr_system=EHRSystem(row["ehr_system"]),
                    last_error=row["last_error"],
                    retry_count=row["retry_count"],
                    dead_lettered_at=row["dead_lettered_at"],
                    reprocessed=row["reprocessed"],
                )
            )
        return results

    async def mark_reprocessed(self, idempotency_key: str) -> None:
        self.store.spark.sql(
            f"UPDATE {self._table} "
            f"SET reprocessed = TRUE "
            f"WHERE idempotency_key = '{idempotency_key}'"
        )
