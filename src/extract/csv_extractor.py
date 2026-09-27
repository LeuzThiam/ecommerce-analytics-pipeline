import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

def extract_sessions(path: Path) -> pd.DataFrame:
    logger.info(f"Extracting sessions from {path}")
    df = pd.read_csv(path)
    logger.info(f"Extracted {len(df)} sessions")
    return df

def extract_pageviews(path: Path) -> pd.DataFrame:
    logger.info(f"Extracting pageviews from {path}")
    df = pd.read_csv(path)
    logger.info(f"Extracted {len(df)} pageviews")
    return df