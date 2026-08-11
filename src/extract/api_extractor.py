import logging
import pandas as pd
import requests

logger = logging.getLogger(__name__)


def extract_orders(base_url: str, page_size: int = 1000) -> pd.DataFrame:
    logger.info(f"Extracting orders from {base_url}")
    all_orders = []
    offset = 0

    while True:
        response = requests.get(f"{base_url}/orders", params={"limit": page_size, "offset": offset})
        response.raise_for_status()
        payload = response.json()
        all_orders.extend(payload["orders"])

        offset += page_size
        if offset >= payload["total"]:
            break

    df = pd.DataFrame(all_orders)
    logger.info(f"Extracted {len(df)} orders")
    return df
