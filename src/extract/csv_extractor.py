import logging
from collections.abc import Iterator
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


def iter_pageview_chunks(
    path: Path,
    chunk_size: int = 100_000,
) -> Iterator[pd.DataFrame]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")

    logger.info("Extracting pageviews from %s in chunks of %s", path, chunk_size)
    for chunk_number, chunk in enumerate(
        pd.read_csv(path, chunksize=chunk_size),
        start=1,
    ):
        logger.info(
            "Extracted pageviews chunk=%s rows=%s",
            chunk_number,
            len(chunk),
        )
        yield chunk
