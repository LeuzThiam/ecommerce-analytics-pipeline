from datetime import datetime

import pandas as pd
import pytest
from fastapi import HTTPException

from api import orders_api


@pytest.fixture
def sample_orders(monkeypatch):
    orders = pd.DataFrame(
        {
            "order_id": [1, 2, 3, 4],
            "created_at": pd.to_datetime(
                [
                    "2026-01-01 10:00:00",
                    "2026-01-01 10:00:00",
                    "2026-01-02 09:00:00",
                    "2026-01-03 12:00:00",
                ]
            ),
            "website_session_id": [11, 12, 13, 14],
            "user_id": [21, 22, 23, 24],
            "primary_product_id": [1, 1, 2, 2],
            "items_purchased": [1, 1, 1, 2],
            "price_usd": [49.99, 49.99, 59.99, 89.99],
            "cogs_usd": [19.49, 19.49, 24.49, 39.49],
        }
    )
    monkeypatch.setattr(orders_api, "orders_df", orders)
    return orders


def test_list_orders_filters_with_date_and_id(sample_orders):
    result = orders_api.list_orders(
        limit=10,
        offset=0,
        created_after=datetime(2026, 1, 1, 10, 0),
        after_id=1,
    )

    assert result["total"] == 3
    assert [order["order_id"] for order in result["orders"]] == [2, 3, 4]


def test_list_orders_applies_pagination_after_filtering(sample_orders):
    result = orders_api.list_orders(
        limit=1,
        offset=1,
        created_after=datetime(2026, 1, 1, 10, 0),
        after_id=1,
    )

    assert result["total"] == 3
    assert [order["order_id"] for order in result["orders"]] == [3]


def test_list_orders_rejects_incomplete_checkpoint(sample_orders):
    with pytest.raises(HTTPException) as error:
        orders_api.list_orders(
            limit=10,
            offset=0,
            created_after=datetime(2026, 1, 1, 10, 0),
            after_id=None,
        )

    assert error.value.status_code == 422


def test_list_orders_serializes_dates(sample_orders):
    result = orders_api.list_orders(
        limit=1,
        offset=0,
        created_after=None,
        after_id=None,
    )

    assert result["orders"][0]["created_at"] == "2026-01-01T10:00:00"


def test_missing_orders_source_returns_service_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(orders_api, "orders_df", None)
    monkeypatch.setattr(orders_api, "DATA_PATH", tmp_path / "missing-orders.csv")

    with pytest.raises(HTTPException) as error:
        orders_api.list_orders(
            limit=10,
            offset=0,
            created_after=None,
            after_id=None,
        )

    assert error.value.status_code == 503
    assert error.value.detail == "Orders source file is unavailable"
