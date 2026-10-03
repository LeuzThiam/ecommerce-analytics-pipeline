from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from src.control.pipeline_runs import PIPELINE_NAME


@dataclass(frozen=True)
class Watermark:
    last_created_at: datetime | None
    last_id: int | None


EMPTY_WATERMARK = Watermark(last_created_at=None, last_id=None)


def ensure_watermarks_table(engine: Engine) -> None:
    """Crée la table de checkpoints si elle n'existe pas encore."""
    statement = text(
        """
        CREATE TABLE IF NOT EXISTS control.etl_watermarks (
            pipeline_name VARCHAR(100) NOT NULL,
            source_name VARCHAR(100) NOT NULL,
            last_created_at TIMESTAMPTZ NOT NULL,
            last_id BIGINT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (pipeline_name, source_name)
        )
        """
    )
    with engine.begin() as connection:
        connection.execute(statement)


def get_watermark(
    engine: Engine,
    source_name: str,
    pipeline_name: str = PIPELINE_NAME,
) -> Watermark:
    """Retourne le dernier checkpoint d'une source ou un checkpoint vide."""
    ensure_watermarks_table(engine)
    statement = text(
        """
        SELECT last_created_at, last_id
        FROM control.etl_watermarks
        WHERE pipeline_name = :pipeline_name
          AND source_name = :source_name
        """
    )
    with engine.connect() as connection:
        row = connection.execute(
            statement,
            {"pipeline_name": pipeline_name, "source_name": source_name},
        ).mappings().one_or_none()

    if row is None:
        return EMPTY_WATERMARK
    return Watermark(
        last_created_at=row["last_created_at"],
        last_id=row["last_id"],
    )


def update_watermark(
    engine: Engine,
    source_name: str,
    last_created_at: datetime,
    last_id: int,
    pipeline_name: str = PIPELINE_NAME,
) -> None:
    """Met à jour un checkpoint dans une transaction autonome."""
    if last_created_at is None or last_id is None:
        raise ValueError("A watermark requires both last_created_at and last_id")

    ensure_watermarks_table(engine)
    with engine.begin() as connection:
        set_watermark(
            connection,
            source_name,
            last_created_at,
            last_id,
            pipeline_name,
        )


def set_watermark(
    connection: Connection,
    source_name: str,
    last_created_at: datetime,
    last_id: int,
    pipeline_name: str = PIPELINE_NAME,
) -> None:
    """Enregistre un checkpoint dans une transaction déjà ouverte.

    Cette variante permet au chargement des données et au checkpoint de partager
    le même COMMIT ou le même ROLLBACK.
    """
    if last_created_at is None or last_id is None:
        raise ValueError("A watermark requires both last_created_at and last_id")

    statement = text(
        """
        INSERT INTO control.etl_watermarks (
            pipeline_name,
            source_name,
            last_created_at,
            last_id
        )
        VALUES (
            :pipeline_name,
            :source_name,
            :last_created_at,
            :last_id
        )
        ON CONFLICT (pipeline_name, source_name)
        DO UPDATE SET
            last_created_at = EXCLUDED.last_created_at,
            last_id = EXCLUDED.last_id,
            updated_at = CURRENT_TIMESTAMP
        """
    )
    connection.execute(
        statement,
        {
            "pipeline_name": pipeline_name,
            "source_name": source_name,
            "last_created_at": last_created_at,
            "last_id": last_id,
        },
    )
