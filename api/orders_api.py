from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Orders API")

DATA_PATH = Path(__file__).parent.parent / "data" / "source" / "orders.csv"
orders_df = pd.read_csv(DATA_PATH)

@app.get("/orders")
def list_orders(limit: int = 10, offset: int = 0):
    page = orders_df.iloc[offset: offset + limit]
    return {
        "total": len(orders_df),
        "limit": limit,
        "offset": offset,
        "orders": page.to_dict(orient="records"),
    }


@app.get("/orders/{order_id}")
def get_order(order_id: int):
    row = orders_df[orders_df["order_id"] == order_id]
    if row.empty:
        raise HTTPException(status_code=404, detail="Order not found")
    return row.to_dict(orient="records")[0]