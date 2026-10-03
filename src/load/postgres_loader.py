import logging
from typing import Literal

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from src.control.watermarks import Watermark, ensure_watermarks_table, set_watermark

logger = logging.getLogger(__name__)


def load_to_staging(
    df: pd.DataFrame,
    table_name: str,
    engine: Engine,
    if_exists: Literal["fail", "replace", "append"] = "replace",
) -> None:
    logger.info(f"Loading {len(df)} rows into staging.{table_name}")
    df.to_sql(
        table_name,
        engine,
        schema="staging",
        if_exists=if_exists,
        index=False,
    )
    logger.info(f"Loaded staging.{table_name}")


def upsert_orders_with_watermark(
    df: pd.DataFrame,
    engine: Engine,
) -> Watermark | None:
    """Charge les commandes et avance leur checkpoint dans une même transaction."""
    required_columns = {
        "order_id",
        "created_at",
        "website_session_id",
        "user_id",
        "primary_product_id",
        "items_purchased",
        "price_usd",
        "cogs_usd",
        "gross_profit",
    }
    missing_columns = required_columns.difference(df.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing order columns for incremental load: {missing}")

    if df.empty:
        with engine.begin() as connection:
            _ensure_orders_staging_table(df, connection)
        logger.info("No new orders to load")
        return None

    ordered = df.sort_values(["created_at", "order_id"])
    latest = ordered.iloc[-1]
    checkpoint = Watermark(
        last_created_at=pd.Timestamp(latest["created_at"]).to_pydatetime(),
        last_id=int(latest["order_id"]),
    )
    records = ordered.where(pd.notna(ordered), None).to_dict(orient="records")

    ensure_watermarks_table(engine)
    with engine.begin() as connection:
        _ensure_orders_staging_table(ordered, connection)
        connection.execute(
            text(
                """
                INSERT INTO staging.orders (
                    order_id,
                    created_at,
                    website_session_id,
                    user_id,
                    primary_product_id,
                    items_purchased,
                    price_usd,
                    cogs_usd,
                    gross_profit
                )
                VALUES (
                    :order_id,
                    :created_at,
                    :website_session_id,
                    :user_id,
                    :primary_product_id,
                    :items_purchased,
                    :price_usd,
                    :cogs_usd,
                    :gross_profit
                )
                ON CONFLICT (order_id)
                DO UPDATE SET
                    created_at = EXCLUDED.created_at,
                    website_session_id = EXCLUDED.website_session_id,
                    user_id = EXCLUDED.user_id,
                    primary_product_id = EXCLUDED.primary_product_id,
                    items_purchased = EXCLUDED.items_purchased,
                    price_usd = EXCLUDED.price_usd,
                    cogs_usd = EXCLUDED.cogs_usd,
                    gross_profit = EXCLUDED.gross_profit
                """
            ),
            records,
        )
        set_watermark(
            connection,
            "orders",
            checkpoint.last_created_at,
            checkpoint.last_id,
        )

    logger.info(
        "Upserted %s orders and advanced checkpoint to (%s, %s)",
        len(ordered),
        checkpoint.last_created_at,
        checkpoint.last_id,
    )
    return checkpoint


def _ensure_orders_staging_table(
    df: pd.DataFrame,
    connection: Connection,
) -> None:
    df.head(0).to_sql(
        "orders",
        connection,
        schema="staging",
        if_exists="append",
        index=False,
    )
    connection.execute(
        text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_staging_orders_order_id
            ON staging.orders (order_id)
            """
        )
    )
