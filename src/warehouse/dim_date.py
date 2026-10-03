from dataclasses import dataclass
from datetime import date

from sqlalchemy import text
from sqlalchemy.engine import Engine


@dataclass(frozen=True)
class DateRange:
    """Bornes calendaires utilisées pour construire la dimension date."""

    start_date: date
    end_date: date


def get_staging_date_range(engine: Engine) -> DateRange:
    """Calcule la plage de dates couverte par les six tables de staging."""
    statement = text(
        """
        WITH source_ranges AS (
            SELECT MIN(created_at)::date AS start_date,
                   MAX(created_at)::date AS end_date
            FROM staging.website_sessions
            UNION ALL
            SELECT MIN(created_at)::date, MAX(created_at)::date
            FROM staging.website_pageviews
            UNION ALL
            SELECT MIN(created_at)::date, MAX(created_at)::date
            FROM staging.products
            UNION ALL
            SELECT MIN(created_at)::date, MAX(created_at)::date
            FROM staging.orders
            UNION ALL
            SELECT MIN(created_at)::date, MAX(created_at)::date
            FROM staging.order_items
            UNION ALL
            SELECT MIN(created_at)::date, MAX(created_at)::date
            FROM staging.order_item_refunds
        )
        SELECT MIN(start_date) AS start_date,
               MAX(end_date) AS end_date
        FROM source_ranges
        """
    )
    with engine.connect() as connection:
        row = connection.execute(statement).mappings().one()

    if row["start_date"] is None or row["end_date"] is None:
        raise ValueError("Cannot build dim_date from empty staging tables")

    return DateRange(
        start_date=row["start_date"],
        end_date=row["end_date"],
    )


def build_dim_date(
    engine: Engine,
    start_date: date,
    end_date: date,
) -> int:
    """Construit une ligne par jour dans ``warehouse.dim_date``.

    L'UPSERT rend la construction idempotente : une nouvelle exécution met à
    jour les dates existantes et ajoute uniquement les jours manquants.
    """
    if start_date > end_date:
        raise ValueError("start_date must be before or equal to end_date")

    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS warehouse"))
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS warehouse.dim_date (
                    date_key INTEGER PRIMARY KEY,
                    date DATE NOT NULL UNIQUE,
                    day SMALLINT NOT NULL,
                    month SMALLINT NOT NULL,
                    month_name VARCHAR(20) NOT NULL,
                    quarter SMALLINT NOT NULL,
                    year SMALLINT NOT NULL,
                    day_of_week SMALLINT NOT NULL,
                    day_name VARCHAR(20) NOT NULL,
                    is_weekend BOOLEAN NOT NULL
                )
                """
            )
        )
        result = connection.execute(
            text(
                """
                INSERT INTO warehouse.dim_date (
                    date_key,
                    date,
                    day,
                    month,
                    month_name,
                    quarter,
                    year,
                    day_of_week,
                    day_name,
                    is_weekend
                )
                SELECT
                    TO_CHAR(calendar_date, 'YYYYMMDD')::integer,
                    calendar_date::date,
                    EXTRACT(DAY FROM calendar_date)::smallint,
                    EXTRACT(MONTH FROM calendar_date)::smallint,
                    CASE EXTRACT(MONTH FROM calendar_date)::integer
                        WHEN 1 THEN 'janvier'
                        WHEN 2 THEN 'février'
                        WHEN 3 THEN 'mars'
                        WHEN 4 THEN 'avril'
                        WHEN 5 THEN 'mai'
                        WHEN 6 THEN 'juin'
                        WHEN 7 THEN 'juillet'
                        WHEN 8 THEN 'août'
                        WHEN 9 THEN 'septembre'
                        WHEN 10 THEN 'octobre'
                        WHEN 11 THEN 'novembre'
                        WHEN 12 THEN 'décembre'
                    END,
                    EXTRACT(QUARTER FROM calendar_date)::smallint,
                    EXTRACT(YEAR FROM calendar_date)::smallint,
                    EXTRACT(ISODOW FROM calendar_date)::smallint,
                    CASE EXTRACT(ISODOW FROM calendar_date)::integer
                        WHEN 1 THEN 'lundi'
                        WHEN 2 THEN 'mardi'
                        WHEN 3 THEN 'mercredi'
                        WHEN 4 THEN 'jeudi'
                        WHEN 5 THEN 'vendredi'
                        WHEN 6 THEN 'samedi'
                        WHEN 7 THEN 'dimanche'
                    END,
                    EXTRACT(ISODOW FROM calendar_date) IN (6, 7)
                FROM GENERATE_SERIES(
                    CAST(:start_date AS date),
                    CAST(:end_date AS date),
                    INTERVAL '1 day'
                ) AS calendar_date
                ON CONFLICT (date_key)
                DO UPDATE SET
                    date = EXCLUDED.date,
                    day = EXCLUDED.day,
                    month = EXCLUDED.month,
                    month_name = EXCLUDED.month_name,
                    quarter = EXCLUDED.quarter,
                    year = EXCLUDED.year,
                    day_of_week = EXCLUDED.day_of_week,
                    day_name = EXCLUDED.day_name,
                    is_weekend = EXCLUDED.is_weekend
                """
            ),
            {
                "start_date": start_date,
                "end_date": end_date,
            },
        )
    return result.rowcount


def build_dim_date_from_staging(engine: Engine) -> tuple[DateRange, int]:
    """Détermine les bornes du staging puis construit la dimension date."""
    date_range = get_staging_date_range(engine)
    affected_rows = build_dim_date(
        engine,
        date_range.start_date,
        date_range.end_date,
    )
    return date_range, affected_rows
