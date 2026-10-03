from datetime import datetime
from unittest.mock import MagicMock, call, patch

import pandas as pd
import pytest

from src.control.pipeline_runs import PipelineRunMetrics
from src.control.watermarks import Watermark
from src.main import process_orders_incrementally


def make_orders() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "order_id": 101,
                "created_at": "2026-01-02T10:00:00",
                "website_session_id": 201,
                "user_id": 301,
                "primary_product_id": 1,
                "items_purchased": 1,
                "price_usd": 49.99,
                "cogs_usd": 19.49,
            }
        ]
    )


@patch("src.main.pd.read_sql")
@patch("src.main.upsert_orders_with_watermark")
@patch("src.main.extract_orders")
@patch("src.main.get_watermark")
def test_failed_run_resumes_from_same_checkpoint(
    mock_get_watermark,
    mock_extract_orders,
    mock_upsert_orders,
    mock_read_sql,
):
    checkpoint = Watermark(datetime(2026, 1, 1, 8, 0), 100)
    mock_get_watermark.return_value = checkpoint
    mock_extract_orders.return_value = make_orders()
    mock_upsert_orders.side_effect = [
        RuntimeError("database unavailable"),
        None,
    ]
    mock_read_sql.return_value = pd.DataFrame({"order_id": [100, 101]})
    engine = MagicMock()
    metrics = PipelineRunMetrics()

    with pytest.raises(RuntimeError, match="database unavailable"):
        process_orders_incrementally(engine, metrics, "run-123")

    assert metrics == PipelineRunMetrics()

    staged_order_ids = process_orders_incrementally(engine, metrics, "run-124")

    assert staged_order_ids == {100, 101}
    assert mock_extract_orders.call_args_list == [
        call(
            "http://localhost:8000",
            created_after=checkpoint.last_created_at,
            after_id=checkpoint.last_id,
        ),
        call(
            "http://localhost:8000",
            created_after=checkpoint.last_created_at,
            after_id=checkpoint.last_id,
        ),
    ]
    assert metrics.rows_extracted == 1
    assert metrics.rows_loaded == 1
    assert metrics.rows_rejected == 0


@patch("src.main.pd.read_sql")
@patch("src.main.upsert_orders_with_watermark")
@patch("src.main.extract_orders")
@patch("src.main.get_watermark")
def test_run_without_new_orders_keeps_existing_staging_ids(
    mock_get_watermark,
    mock_extract_orders,
    mock_upsert_orders,
    mock_read_sql,
):
    mock_get_watermark.return_value = Watermark(
        datetime(2026, 1, 2, 10, 0),
        101,
    )
    mock_extract_orders.return_value = make_orders().iloc[0:0]
    mock_read_sql.return_value = pd.DataFrame({"order_id": [100, 101]})
    metrics = PipelineRunMetrics()

    staged_order_ids = process_orders_incrementally(
        MagicMock(),
        metrics,
        "run-123",
    )

    assert staged_order_ids == {100, 101}
    mock_upsert_orders.assert_called_once()
    assert metrics == PipelineRunMetrics()
