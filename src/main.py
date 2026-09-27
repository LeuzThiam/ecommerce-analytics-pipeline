import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine

from src.extract.api_extractor import extract_orders
from src.extract.csv_extractor import extract_pageviews, extract_sessions
from src.extract.json_extractor import extract_products
from src.extract.sql_extractor import extract_order_items, extract_refunds
from src.load.postgres_loader import load_to_staging
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
    logger.info("PIPELINE STARTED")

    sessions = extract_sessions(DATA_SOURCE_DIR / "website_sessions.csv")
    valid_sessions, rejected_sessions = validate_sessions(sessions)
    logger.info(f"sessions: valid={len(valid_sessions)} rejected={len(rejected_sessions)}")
    load_to_staging(transform_sessions(valid_sessions), "website_sessions", engine)

    pageviews = extract_pageviews(DATA_SOURCE_DIR / "website_pageviews.csv")
    valid_pageviews, rejected_pageviews = validate_pageviews(pageviews)
    logger.info(f"pageviews: valid={len(valid_pageviews)} rejected={len(rejected_pageviews)}")
    load_to_staging(transform_pageviews(valid_pageviews), "website_pageviews", engine)

    products = extract_products(DATA_SOURCE_DIR / "products.json")
    valid_products, rejected_products = validate_products(products)
    logger.info(f"products: valid={len(valid_products)} rejected={len(rejected_products)}")
    load_to_staging(transform_products(valid_products), "products", engine)

    orders = extract_orders(ORDERS_API_BASE_URL)
    valid_orders, rejected_orders = validate_orders(orders)
    logger.info(f"orders: valid={len(valid_orders)} rejected={len(rejected_orders)}")
    load_to_staging(transform_orders(valid_orders), "orders", engine)

    order_items = extract_order_items(engine)
    valid_items, rejected_items = validate_order_items(
        order_items, set(valid_orders["order_id"]), set(valid_products["product_id"])
    )
    logger.info(f"order_items: valid={len(valid_items)} rejected={len(rejected_items)}")
    load_to_staging(transform_order_items(valid_items), "order_items", engine)

    refunds = extract_refunds(engine)
    valid_refunds, rejected_refunds = validate_refunds(
        refunds, set(valid_items["order_item_id"]), set(valid_orders["order_id"])
    )
    logger.info(f"refunds: valid={len(valid_refunds)} rejected={len(rejected_refunds)}")
    load_to_staging(transform_refunds(valid_refunds), "order_item_refunds", engine)

    logger.info("LOAD COMPLETED")


if __name__ == "__main__":
    run()