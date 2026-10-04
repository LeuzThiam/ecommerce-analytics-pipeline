from contextlib import contextmanager
from dataclasses import dataclass
from time import perf_counter
from typing import Iterator
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Engine


PIPELINE_NAME = "ecommerce_analytics"
VALID_STATUSES = {"SUCCESS", "FAILED"}


@dataclass
class PipelineRunMetrics:
    """Cumule les volumes traités pendant une exécution du pipeline."""
    rows_extracted: int = 0
    rows_loaded: int = 0
    rows_rejected: int = 0

    def record(self, extracted: int, loaded: int, rejected: int) -> None:
        """Ajoute les métriques d'une source ou d'un lot aux totaux."""
        self.rows_extracted += extracted
        self.rows_loaded += loaded
        self.rows_rejected += rejected


@dataclass
class PipelineStepMetrics:
    """Cumule le volume traité par une étape technique du pipeline."""

    rows_processed: int = 0

    def record(self, rows: int) -> None:
        """Ajoute un volume au compteur de l'étape."""
        self.rows_processed += rows


@dataclass(frozen=True)
class PipelineStepSummary:
    """Décrit le résultat persistant d'une étape d'exécution."""

    step_name: str
    status: str
    duration_seconds: float
    rows_processed: int


def ensure_pipeline_runs_table(engine: Engine) -> None:
    """Crée la table d'historique des exécutions si nécessaire."""
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


def ensure_pipeline_step_runs_table(engine: Engine) -> None:
    """Crée le détail de monitoring des étapes et son index de lecture."""
    table_statement = text(
        """
        CREATE TABLE IF NOT EXISTS control.pipeline_step_runs (
            step_run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            run_id UUID NOT NULL REFERENCES control.pipeline_runs(run_id),
            step_name VARCHAR(100) NOT NULL,
            started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            finished_at TIMESTAMPTZ,
            status VARCHAR(20) NOT NULL,
            duration_seconds NUMERIC(12, 3),
            rows_processed BIGINT NOT NULL DEFAULT 0,
            error_message TEXT,
            CONSTRAINT pipeline_step_runs_status_check
                CHECK (status IN ('STARTED', 'SUCCESS', 'FAILED'))
        )
        """
    )
    index_statement = text(
        """
        CREATE INDEX IF NOT EXISTS idx_pipeline_step_runs_run_id
        ON control.pipeline_step_runs (run_id, step_run_id)
        """
    )
    with engine.begin() as connection:
        connection.execute(table_statement)
        connection.execute(index_statement)


def start_pipeline_run(engine: Engine, pipeline_name: str = PIPELINE_NAME) -> str:
    """Crée une exécution au statut ``STARTED`` et retourne son identifiant."""
    ensure_pipeline_runs_table(engine)
    ensure_pipeline_step_runs_table(engine)
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


@contextmanager
def track_pipeline_step(
    engine: Engine,
    run_id: str,
    step_name: str,
) -> Iterator[PipelineStepMetrics]:
    """Suit une étape et persiste automatiquement son résultat final."""
    insert_statement = text(
        """
        INSERT INTO control.pipeline_step_runs (run_id, step_name, status)
        VALUES (:run_id, :step_name, 'STARTED')
        RETURNING step_run_id
        """
    )
    with engine.begin() as connection:
        step_run_id = connection.execute(
            insert_statement,
            {"run_id": run_id, "step_name": step_name},
        ).scalar_one()

    metrics = PipelineStepMetrics()
    started_at = perf_counter()
    try:
        yield metrics
    except Exception as error:
        _finish_pipeline_step(
            engine,
            step_run_id,
            "FAILED",
            metrics,
            perf_counter() - started_at,
            str(error),
        )
        raise
    else:
        _finish_pipeline_step(
            engine,
            step_run_id,
            "SUCCESS",
            metrics,
            perf_counter() - started_at,
        )


def _finish_pipeline_step(
    engine: Engine,
    step_run_id: int,
    status: str,
    metrics: PipelineStepMetrics,
    duration_seconds: float,
    error_message: str | None = None,
) -> None:
    """Finalise une étape sans exposer cette opération au pipeline principal."""
    statement = text(
        """
        UPDATE control.pipeline_step_runs
        SET finished_at = CURRENT_TIMESTAMP,
            status = :status,
            duration_seconds = :duration_seconds,
            rows_processed = :rows_processed,
            error_message = :error_message
        WHERE step_run_id = :step_run_id
        """
    )
    with engine.begin() as connection:
        connection.execute(
            statement,
            {
                "step_run_id": step_run_id,
                "status": status,
                "duration_seconds": round(duration_seconds, 3),
                "rows_processed": metrics.rows_processed,
                "error_message": error_message,
            },
        )


def get_pipeline_step_summaries(
    engine: Engine,
    run_id: str,
) -> list[PipelineStepSummary]:
    """Retourne les étapes d'une exécution dans leur ordre de lancement."""
    statement = text(
        """
        SELECT step_name, status, duration_seconds, rows_processed
        FROM control.pipeline_step_runs
        WHERE run_id = :run_id
        ORDER BY step_run_id
        """
    )
    with engine.connect() as connection:
        rows = connection.execute(statement, {"run_id": run_id}).mappings().all()

    return [
        PipelineStepSummary(
            step_name=row["step_name"],
            status=row["status"],
            duration_seconds=float(row["duration_seconds"] or 0),
            rows_processed=row["rows_processed"],
        )
        for row in rows
    ]


def finish_pipeline_run(
    engine: Engine,
    run_id: str,
    status: str,
    metrics: PipelineRunMetrics,
    error_message: str | None = None,
) -> None:
    """Finalise une exécution avec son statut, ses métriques et son erreur."""
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
