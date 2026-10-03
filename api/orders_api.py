from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Query

app = FastAPI(title="Orders API")

DATA_PATH = Path(__file__).parent.parent / "data" / "source" / "orders.csv"
orders_df: pd.DataFrame | None = None


def get_orders_df() -> pd.DataFrame:
    """Charge la source au premier appel afin de garder le module importable sans données."""
    global orders_df

    if orders_df is not None:
        return orders_df
    if not DATA_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="Orders source file is unavailable",
        )

    orders_df = pd.read_csv(DATA_PATH, parse_dates=["created_at"])
    orders_df = orders_df.sort_values(["created_at", "order_id"]).reset_index(drop=True)
    return orders_df


def serialize_orders(df: pd.DataFrame) -> list[dict]:
    serialized = df.copy()
    serialized["created_at"] = serialized["created_at"].map(
        lambda value: pd.Timestamp(value).isoformat()
    )
    return serialized.to_dict(orient="records")


@app.get("/orders")
def list_orders(
    limit: int = Query(default=1000, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    created_after: datetime | None = None,
    after_id: int | None = None,
):
    if (created_after is None) != (after_id is None):
        raise HTTPException(
            status_code=422,
            detail="created_after and after_id must be provided together",
        )

    source_orders = get_orders_df()
    filtered_orders = source_orders

    if created_after is not None and after_id is not None:
        checkpoint_date = pd.Timestamp(created_after)
        if checkpoint_date.tzinfo is not None:
            checkpoint_date = checkpoint_date.tz_convert("UTC").tz_localize(None)

        filtered_orders = source_orders[
            (source_orders["created_at"] > checkpoint_date)
            | (
                (source_orders["created_at"] == checkpoint_date)
                & (source_orders["order_id"] > after_id)
            )
        ]

    page = filtered_orders.iloc[offset : offset + limit]
    return {
        "total": len(filtered_orders),
        "limit": limit,
        "offset": offset,
        "orders": serialize_orders(page),
    }


@app.get("/orders/{order_id}")
def get_order(order_id: int):
    source_orders = get_orders_df()
    row = source_orders[source_orders["order_id"] == order_id]
    if row.empty:
        raise HTTPException(status_code=404, detail="Order not found")
    return serialize_orders(row)[0]
