from datetime import datetime
from unittest.mock import MagicMock, call, patch

import pytest

from src.extract.api_extractor import ORDER_COLUMNS, extract_orders


def make_response(total, orders):
    response = MagicMock()
    response.json.return_value = {"total": total, "orders": orders}
    return response


@patch("src.extract.api_extractor.requests.get")
def test_extract_orders_paginates_with_received_row_count(mock_get):
    mock_get.side_effect = [
        make_response(3, [{"order_id": 1}, {"order_id": 2}]),
        make_response(3, [{"order_id": 3}]),
    ]

    result = extract_orders("http://localhost:8000", page_size=2)

    assert result["order_id"].tolist() == [1, 2, 3]
    assert mock_get.call_args_list == [
        call(
            "http://localhost:8000/orders",
            params={"limit": 2, "offset": 0},
            timeout=30,
        ),
        call(
            "http://localhost:8000/orders",
            params={"limit": 2, "offset": 2},
            timeout=30,
        ),
    ]


@patch("src.extract.api_extractor.requests.get")
def test_extract_orders_sends_checkpoint_parameters(mock_get):
    mock_get.return_value = make_response(0, [])
    checkpoint_date = datetime(2026, 1, 1, 10, 0)

    extract_orders(
        "http://localhost:8000",
        created_after=checkpoint_date,
        after_id=42,
    )

    mock_get.assert_called_once_with(
        "http://localhost:8000/orders",
        params={
            "limit": 1000,
            "offset": 0,
            "created_after": "2026-01-01T10:00:00",
            "after_id": 42,
        },
        timeout=30,
    )


@patch("src.extract.api_extractor.requests.get")
def test_extract_orders_preserves_columns_when_no_rows(mock_get):
    mock_get.return_value = make_response(0, [])

    result = extract_orders("http://localhost:8000")

    assert result.empty
    assert result.columns.tolist() == ORDER_COLUMNS


def test_extract_orders_rejects_incomplete_checkpoint():
    with pytest.raises(ValueError, match="must be provided together"):
        extract_orders(
            "http://localhost:8000",
            created_after=datetime(2026, 1, 1, 10, 0),
        )
