from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Engine


PIPELINE_NAME = "ecommerce_analytics"
VALID_STATUSES = {"SUCCESS", "FAILED"}


@dataclass
class PipelineRunMetrics:
    rows_extracted: int = 0
    rows_loaded: int = 0
    rows_rejected: int = 0

    def record(self, extracted: int, loaded: int, rejected: int) -> None:
        self.rows_extracted += extracted
        self.rows_loaded += loaded
        self.rows_rejected += rejected


def ensure_pipeline_runs_table(engine: Engine) -> None:
    statement = text(
        """
        CREATE TABLE IF NOT EXISTS control.pipeline_runs (
            run_id UUID PRIMARY KEY,
            pipeline_name VARCHAR(100) NOT NULL,
            started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            finished_at TIMESTAMPTZ,
            status VARCHAR(20) NOT NULL,
            rows_extracted BIGINT NOT NULL DEFAULT 0,
            rows_loaded BIGINT NOT NULL DEFAULT 0,
            rows_rejected BIGINT NOT NULL DEFAULT 0,
            error_message TEXT,
            CONSTRAINT pipeline_runs_status_check
                CHECK (status IN ('STARTED', 'SUCCESS', 'FAILED'))
        )
        """
    )
    with engine.begin() as connection:
        connection.execute(statement)


def start_pipeline_run(engine: Engine, pipeline_name: str = PIPELINE_NAME) -> str:
    ensure_pipeline_runs_table(engine)
    run_id = str(uuid4())
    statement = text(
        """
        INSERT INTO control.pipeline_runs (run_id, pipeline_name, status)
        VALUES (:run_id, :pipeline_name, 'STARTED')
        """
    )
    with engine.begin() as connection:
        connection.execute(
            statement,
            {"run_id": run_id, "pipeline_name": pipeline_name},
        )
    return run_id


def finish_pipeline_run(
    engine: Engine,
    run_id: str,
    status: str,
    metrics: PipelineRunMetrics,
    error_message: str | None = None,
) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"Unsupported pipeline status: {status}")

    statement = text(
        """
        UPDATE control.pipeline_runs
        SET finished_at = CURRENT_TIMESTAMP,
            status = :status,
            rows_extracted = :rows_extracted,
            rows_loaded = :rows_loaded,
            rows_rejected = :rows_rejected,
            error_message = :error_message
        WHERE run_id = :run_id
        """
    )
    with engine.begin() as connection:
        connection.execute(
            statement,
            {
                "run_id": run_id,
                "status": status,
                "rows_extracted": metrics.rows_extracted,
                "rows_loaded": metrics.rows_loaded,
                "rows_rejected": metrics.rows_rejected,
                "error_message": error_message,
            },
        )
