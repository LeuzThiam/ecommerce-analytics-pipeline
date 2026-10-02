from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.control.watermarks import Watermark
from src.load.postgres_loader import upsert_orders_with_watermark


def make_orders() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "order_id": 11,
                "created_at": datetime(2026, 1, 2, 10, 0),
                "website_session_id": 101,
                "user_id": 201,
                "primary_product_id": 1,
                "items_purchased": 1,
                "price_usd": 49.99,
                "cogs_usd": 19.49,
                "gross_profit": 30.50,
            },
            {
                "order_id": 12,
                "created_at": datetime(2026, 1, 2, 10, 0),
                "website_session_id": 102,
                "user_id": 202,
                "primary_product_id": 2,
                "items_purchased": 2,
                "price_usd": 89.99,
                "cogs_usd": 35.00,
                "gross_profit": 54.99,
            },
        ]
    )


@patch("src.load.postgres_loader.ensure_watermarks_table")
@patch("src.load.postgres_loader.set_watermark")
@patch("pandas.DataFrame.to_sql")
def test_upsert_orders_and_checkpoint_share_one_transaction(
    mock_to_sql,
    mock_set_watermark,
    mock_ensure_watermarks,
):
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    checkpoint = upsert_orders_with_watermark(make_orders(), engine)

    assert checkpoint == Watermark(datetime(2026, 1, 2, 10, 0), 12)
    mock_ensure_watermarks.assert_called_once_with(engine)
    mock_to_sql.assert_called_once_with(
        "orders",
        connection,
        schema="staging",
        if_exists="append",
        index=False,
    )
    assert connection.execute.call_count == 2
    mock_set_watermark.assert_called_once_with(
        connection,
        "orders",
        datetime(2026, 1, 2, 10, 0),
        12,
    )


@patch("src.load.postgres_loader.ensure_watermarks_table")
def test_empty_increment_does_not_open_transaction(mock_ensure_watermarks):
    engine = MagicMock()

    checkpoint = upsert_orders_with_watermark(pd.DataFrame(), engine)

    assert checkpoint is None
    engine.begin.assert_not_called()
    mock_ensure_watermarks.assert_not_called()


@patch("src.load.postgres_loader.ensure_watermarks_table")
@patch("src.load.postgres_loader.set_watermark")
@patch("pandas.DataFrame.to_sql")
def test_checkpoint_is_not_advanced_when_upsert_fails(
    mock_to_sql,
    mock_set_watermark,
    mock_ensure_watermarks,
):
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    connection.execute.side_effect = [None, RuntimeError("database unavailable")]

    with pytest.raises(RuntimeError, match="database unavailable"):
        upsert_orders_with_watermark(make_orders(), engine)

    mock_set_watermark.assert_not_called()


def test_incremental_load_rejects_missing_columns():
    with pytest.raises(ValueError, match="Missing order columns"):
        upsert_orders_with_watermark(
            pd.DataFrame([{"order_id": 1}]),
            MagicMock(),
        )
