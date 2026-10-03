from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.control.watermarks import (
    EMPTY_WATERMARK,
    Watermark,
    get_watermark,
    update_watermark,
)


@patch("src.control.watermarks.ensure_watermarks_table")
def test_get_watermark_returns_empty_value_when_missing(mock_ensure_table):
    engine = MagicMock()
    result = engine.connect.return_value.__enter__.return_value.execute.return_value
    result.mappings.return_value.one_or_none.return_value = None

    watermark = get_watermark(engine, "orders")

    assert watermark == EMPTY_WATERMARK
    mock_ensure_table.assert_called_once_with(engine)


@patch("src.control.watermarks.ensure_watermarks_table")
def test_get_watermark_returns_stored_value(mock_ensure_table):
    checkpoint_date = datetime(2026, 9, 27, 13, 0, tzinfo=UTC)
    engine = MagicMock()
    result = engine.connect.return_value.__enter__.return_value.execute.return_value
    result.mappings.return_value.one_or_none.return_value = {
        "last_created_at": checkpoint_date,
        "last_id": 42,
    }

    watermark = get_watermark(engine, "orders")

    assert watermark == Watermark(checkpoint_date, 42)


@patch("src.control.watermarks.ensure_watermarks_table")
def test_update_watermark_upserts_checkpoint(mock_ensure_table):
    checkpoint_date = datetime(2026, 9, 27, 13, 0, tzinfo=UTC)
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    update_watermark(engine, "orders", checkpoint_date, 42)

    mock_ensure_table.assert_called_once_with(engine)
    parameters = connection.execute.call_args.args[1]
    assert parameters == {
        "pipeline_name": "ecommerce_analytics",
        "source_name": "orders",
        "last_created_at": checkpoint_date,
        "last_id": 42,
    }


def test_update_watermark_rejects_incomplete_checkpoint():
    with pytest.raises(ValueError, match="requires both"):
        update_watermark(MagicMock(), "orders", None, 42)
