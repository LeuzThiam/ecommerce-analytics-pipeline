import pandas as pd

from src.validation.orders_rules import validate_orders


def test_negative_price_is_rejected():
    df = pd.DataFrame(
        {
            "order_id": [1, 2],
            "website_session_id": [10, 20],
            "user_id": [10, 20],
            "items_purchased": [1, 1],
            "price_usd": [49.99, -10.0],
            "cogs_usd": [19.49, 5.0],
        }
    )
    valid, rejected = validate_orders(df)
    assert len(valid) == 1
    assert len(rejected) == 1
    assert rejected.iloc[0]["order_id"] == 2


def test_duplicate_order_id_is_rejected():
    df = pd.DataFrame(
        {
            "order_id": [1, 1],
            "website_session_id": [10, 20],
            "user_id": [10, 20],
            "items_purchased": [1, 1],
            "price_usd": [49.99, 49.99],
            "cogs_usd": [19.49, 19.49],
        }
    )
    valid, rejected = validate_orders(df)
    assert len(valid) == 1
    assert len(rejected) == 1