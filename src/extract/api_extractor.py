import logging
import time
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
    max_attempts: int = 3,
    retry_delay_seconds: float = 1.0,
) -> pd.DataFrame:
    """Extrait toutes les pages de commandes disponibles après un checkpoint.

    Les appels HTTP temporaires en échec sont rejoués par
    :func:`_request_orders_page`. Un DataFrame vide conserve toujours le schéma
    attendu afin que les étapes suivantes du pipeline restent prévisibles.
    """
    if (created_after is None) != (after_id is None):
        raise ValueError("created_after and after_id must be provided together")
    if max_attempts <= 0:
        raise ValueError("max_attempts must be greater than zero")
    if retry_delay_seconds < 0:
        raise ValueError("retry_delay_seconds cannot be negative")

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

        response = _request_orders_page(
            f"{base_url}/orders",
            params,
            max_attempts,
            retry_delay_seconds,
        )
        payload = response.json()
        orders = payload["orders"]
        all_orders.extend(orders)

        offset += len(orders)
        if offset >= payload["total"] or not orders:
            break

    df = pd.DataFrame(all_orders, columns=ORDER_COLUMNS)
    logger.info("Extracted %s orders", len(df))
    return df


def _request_orders_page(
    url: str,
    params: dict,
    max_attempts: int,
    retry_delay_seconds: float,
) -> requests.Response:
    """Appelle une page de l'API avec retry ciblé et backoff exponentiel."""
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response
        except requests.RequestException as error:
            status_code = (
                error.response.status_code
                if error.response is not None
                else None
            )
            # Les erreurs 4xx sont définitives ; seules les pannes temporaires
            # et les réponses serveur 5xx justifient une nouvelle tentative.
            is_temporary = isinstance(
                error,
                (requests.Timeout, requests.ConnectionError),
            ) or (status_code is not None and 500 <= status_code < 600)

            if not is_temporary or attempt == max_attempts:
                logger.error(
                    "Orders API request failed attempt=%s/%s status=%s",
                    attempt,
                    max_attempts,
                    status_code,
                )
                raise

            # 1 s, 2 s, 4 s... selon le délai initial configuré.
            delay = retry_delay_seconds * (2 ** (attempt - 1))
            logger.warning(
                "Orders API request failed attempt=%s/%s status=%s retry_in=%ss",
                attempt,
                max_attempts,
                status_code,
                delay,
            )
            time.sleep(delay)

    raise RuntimeError("Orders API retry loop ended unexpectedly")
