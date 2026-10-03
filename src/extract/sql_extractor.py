import logging
import pandas as pd
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

def extract_order_items(engine: Engine) -> pd.DataFrame:
    """Extrait les articles commandés depuis le schéma PostgreSQL ``source``."""
    logger.info("Extracting order_items from PostgreSQL")
    df = pd.read_sql("SELECT * FROM source.order_items", engine)
    logger.info(f"Extracted {len(df)} order_items")
    return df


def extract_refunds(engine: Engine) -> pd.DataFrame:
    """Extrait les remboursements depuis le schéma PostgreSQL ``source``."""
    logger.info("Extracting order_item_refunds from PostgreSQL")
    df = pd.read_sql("SELECT * FROM source.order_item_refunds", engine)
    logger.info(f"Extracted {len(df)} order_item_refunds")
    return df
