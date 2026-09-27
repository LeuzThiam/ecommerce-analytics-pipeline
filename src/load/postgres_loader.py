import logging

import pandas as pd
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def load_to_staging(df: pd.DataFrame, table_name: str, engine: Engine) -> None:
    logger.info(f"Loading {len(df)} rows into staging.{table_name}")
    df.to_sql(table_name, engine, schema="staging", if_exists="replace", index=False)
    logger.info(f"Loaded staging.{table_name}")