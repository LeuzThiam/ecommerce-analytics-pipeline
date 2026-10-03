import logging
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

def extract_products(path: Path) -> pd.DataFrame:
    """Charge le catalogue des produits depuis sa source JSON."""
    logger.info(f"Extracting products from {path}")
    df = pd.read_json(path)
    logger.info(f"Extracted {len(df)} products")
    return df
