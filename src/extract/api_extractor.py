import logging
from datetime import datetime

import pandas as pd
import requests

logger = logging.getLogger(__name__)

ORDER_COLUMNS = [
    "order_id",
    "created_at",
    "website_session_id",
    "user_id",
    "primary_product_id",
    "items_purchased",
    "price_usd",
    "cogs_usd",
]


def extract_orders(
    base_url: str,
    page_size: int = 1000,
    created_after: datetime | None = None,
    after_id: int | None = None,
) -> pd.DataFrame:
    if (created_after is None) != (after_id is None):
        raise ValueError("created_after and after_id must be provided together")

    logger.info(
        "Extracting orders from %s created_after=%s after_id=%s",
        base_url,
        created_after,
        after_id,
    )
    all_orders = []
    offset = 0

    while True:
        params = {"limit": page_size, "offset": offset}

        if created_after is not None and after_id is not None:
            params["created_after"] = created_after.isoformat()
            params["after_id"] = after_id

        response = requests.get(
            f"{base_url}/orders",
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        orders = payload["orders"]
        all_orders.extend(orders)

        offset += len(orders)
        if offset >= payload["total"] or not orders:
            break

    df = pd.DataFrame(all_orders, columns=ORDER_COLUMNS)
    logger.info("Extracted %s orders", len(df))
    return df
