import logging
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

from src.control.pipeline_runs import (
    PipelineRunMetrics,
    finish_pipeline_run,
    start_pipeline_run,
)
from src.control.watermarks import get_watermark
from src.extract.api_extractor import extract_orders
from src.extract.csv_extractor import extract_pageviews, extract_sessions
from src.extract.json_extractor import extract_products
from src.extract.sql_extractor import extract_order_items, extract_refunds
from src.load.postgres_loader import load_to_staging, upsert_orders_with_watermark
from src.transform.order_items import transform_order_items
from src.transform.orders import transform_orders
from src.transform.pageviews import transform_pageviews
from src.transform.products import transform_products
from src.transform.refunds import transform_refunds
from src.transform.sessions import transform_sessions
from src.validation.order_items_rules import validate_order_items
from src.validation.orders_rules import validate_orders
from src.validation.pageviews_rules import validate_pageviews
from src.validation.products_rules import validate_products
from src.validation.refunds_rules import validate_refunds
from src.validation.sessions_rules import validate_sessions

DATA_SOURCE_DIR = Path(__file__).parent.parent / "data" / "source"
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

load_dotenv()

ORDERS_API_BASE_URL = os.getenv("ORDERS_API_BASE_URL", "http://localhost:8000")
POSTGRES_URL = (
    f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
    f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "pipeline.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def run() -> None:
    engine = create_engine(POSTGRES_URL)
    metrics = PipelineRunMetrics()
    run_id = start_pipeline_run(engine)
    logger.info(f"PIPELINE STARTED run_id={run_id}")

    try:
        sessions = extract_sessions(DATA_SOURCE_DIR / "website_sessions.csv")
        valid_sessions, rejected_sessions = validate_sessions(sessions)
        logger.info(f"sessions: valid={len(valid_sessions)} rejected={len(rejected_sessions)}")
        load_to_staging(transform_sessions(valid_sessions), "website_sessions", engine)
        metrics.record(len(sessions), len(valid_sessions), len(rejected_sessions))

        pageviews = extract_pageviews(DATA_SOURCE_DIR / "website_pageviews.csv")
        valid_pageviews, rejected_pageviews = validate_pageviews(pageviews)
        logger.info(f"pageviews: valid={len(valid_pageviews)} rejected={len(rejected_pageviews)}")
        load_to_staging(transform_pageviews(valid_pageviews), "website_pageviews", engine)
        metrics.record(len(pageviews), len(valid_pageviews), len(rejected_pageviews))

        products = extract_products(DATA_SOURCE_DIR / "products.json")
        valid_products, rejected_products = validate_products(products)
        logger.info(f"products: valid={len(valid_products)} rejected={len(rejected_products)}")
        load_to_staging(transform_products(valid_products), "products", engine)
        metrics.record(len(products), len(valid_products), len(rejected_products))

        orders_watermark = get_watermark(engine, "orders")
        orders = extract_orders(
            ORDERS_API_BASE_URL,
            created_after=orders_watermark.last_created_at,
            after_id=orders_watermark.last_id,
        )
        valid_orders, rejected_orders = validate_orders(orders)
        logger.info(f"orders: valid={len(valid_orders)} rejected={len(rejected_orders)}")
        upsert_orders_with_watermark(transform_orders(valid_orders), engine)
        metrics.record(len(orders), len(valid_orders), len(rejected_orders))

        staged_order_ids = set(
            pd.read_sql("SELECT order_id FROM staging.orders", engine)["order_id"]
        )
        order_items = extract_order_items(engine)
        valid_items, rejected_items = validate_order_items(
            order_items, staged_order_ids, set(valid_products["product_id"])
        )
        logger.info(f"order_items: valid={len(valid_items)} rejected={len(rejected_items)}")
        load_to_staging(transform_order_items(valid_items), "order_items", engine)
        metrics.record(len(order_items), len(valid_items), len(rejected_items))

        refunds = extract_refunds(engine)
        valid_refunds, rejected_refunds = validate_refunds(
            refunds, set(valid_items["order_item_id"]), staged_order_ids
        )
        logger.info(f"refunds: valid={len(valid_refunds)} rejected={len(rejected_refunds)}")
        load_to_staging(transform_refunds(valid_refunds), "order_item_refunds", engine)
        metrics.record(len(refunds), len(valid_refunds), len(rejected_refunds))

        finish_pipeline_run(engine, run_id, "SUCCESS", metrics)
        logger.info(f"LOAD COMPLETED run_id={run_id}")
    except Exception as error:
        logger.exception(f"PIPELINE FAILED run_id={run_id}")
        try:
            finish_pipeline_run(engine, run_id, "FAILED", metrics, str(error))
        except Exception:
            logger.exception(f"FAILED TO UPDATE PIPELINE RUN run_id={run_id}")
        raise


if __name__ == "__main__":
    run()
