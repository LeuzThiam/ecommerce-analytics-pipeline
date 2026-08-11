import pandas as pd
import pytest

from src.transform.orders import transform_orders


def test_gross_profit_calculation():
    df = pd.DataFrame(
        {
            "created_at": ["2012-03-19 10:42:46"],
            "price_usd": [49.99],
            "cogs_usd": [19.49],
        }
    )
    result = transform_orders(df)
    assert result["gross_profit"].iloc[0] == pytest.approx(30.5)
    assert pd.api.types.is_datetime64_any_dtype(result["created_at"])