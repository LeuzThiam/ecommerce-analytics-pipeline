import logging
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from src.control.pipeline_runs import (
    PipelineRunMetrics,
    finish_pipeline_run,
    get_pipeline_step_summaries,
    start_pipeline_run,
    track_pipeline_step,
)
from src.control.watermarks import get_watermark
from src.extract.api_extractor import extract_orders
from src.extract.csv_extractor import extract_sessions, iter_pageview_chunks
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
from src.validation.quarantine import quarantine_rejected_rows
from src.validation.refunds_rules import validate_refunds
from src.validation.sessions_rules import validate_sessions
from src.warehouse.build import build_warehouse

DATA_SOURCE_DIR = Path(__file__).parent.parent / "data" / "source"
LOG_DIR = Path(__file__).parent.parent / "logs"
REJECTED_DIR = Path(__file__).parent.parent / "data" / "rejected"
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


def log_pipeline_summary(
    engine: Engine,
    run_id: str,
    status: str,
    metrics: PipelineRunMetrics,
) -> None:
    """Écrit un bilan compact du run et de chacune de ses étapes."""
    lines = [
        "================================================",
        "ECOMMERCE ANALYTICS PIPELINE",
        f"run_id={run_id} status={status}",
        (
            f"extracted={metrics.rows_extracted} "
            f"loaded={metrics.rows_loaded} rejected={metrics.rows_rejected}"
        ),
    ]
    for step in get_pipeline_step_summaries(engine, run_id):
        lines.append(
            f"{step.step_name}: status={step.status} "
            f"duration={step.duration_seconds:.3f}s rows={step.rows_processed}"
        )
    lines.append("================================================")
    logger.info("\n%s", "\n".join(lines))


def process_pageview_chunks(
    engine: Engine,
    metrics: PipelineRunMetrics,
    run_id: str,
) -> None:
    """Valide, transforme et charge les pageviews lot par lot."""
    first_chunk = True

    for chunk_number, pageviews in enumerate(
        iter_pageview_chunks(DATA_SOURCE_DIR / "website_pageviews.csv"),
        start=1,
    ):
        valid_pageviews, rejected_pageviews = validate_pageviews(pageviews)
        logger.info(
            "pageviews: chunk=%s valid=%s rejected=%s",
            chunk_number,
            len(valid_pageviews),
            len(rejected_pageviews),
        )
        quarantine_rejected_rows(
            rejected_pageviews,
            "website_pageviews",
            run_id,
            REJECTED_DIR,
        )
        # Le premier lot reconstruit la table ; les suivants la complètent.
        load_to_staging(
            transform_pageviews(valid_pageviews),
            "website_pageviews",
            engine,
            if_exists="replace" if first_chunk else "append",
        )
        metrics.record(
            len(pageviews),
            len(valid_pageviews),
            len(rejected_pageviews),
        )
        first_chunk = False


def process_orders_incrementally(
    engine: Engine,
    metrics: PipelineRunMetrics,
    run_id: str,
) -> set[int]:
    """Traite les nouvelles commandes et retourne tous les IDs déjà chargés.

    Les métriques sont enregistrées uniquement après la réussite de l'UPSERT et
    de la mise à jour atomique du checkpoint.
    """
    watermark = get_watermark(engine, "orders")
    orders = extract_orders(
        ORDERS_API_BASE_URL,
        created_after=watermark.last_created_at,
        after_id=watermark.last_id,
    )
    valid_orders, rejected_orders = validate_orders(orders)
    logger.info(
        "orders: valid=%s rejected=%s",
        len(valid_orders),
        len(rejected_orders),
    )
    quarantine_rejected_rows(
        rejected_orders,
        "orders",
        run_id,
        REJECTED_DIR,
    )

    upsert_orders_with_watermark(transform_orders(valid_orders), engine)
    metrics.record(len(orders), len(valid_orders), len(rejected_orders))

    return set(
        pd.read_sql("SELECT order_id FROM staging.orders", engine)["order_id"]
    )


def run() -> str:
    """Exécute le pipeline complet et retourne l'identifiant de son run."""
    engine = create_engine(POSTGRES_URL)
    metrics = PipelineRunMetrics()
    run_id = start_pipeline_run(engine)
    logger.info(f"PIPELINE STARTED run_id={run_id}")

    try:
        with track_pipeline_step(engine, run_id, "staging_sessions") as step:
            sessions = extract_sessions(DATA_SOURCE_DIR / "website_sessions.csv")
            valid_sessions, rejected_sessions = validate_sessions(sessions)
            logger.info(
                "sessions: valid=%s rejected=%s",
                len(valid_sessions),
                len(rejected_sessions),
            )
            quarantine_rejected_rows(
                rejected_sessions, "website_sessions", run_id, REJECTED_DIR
            )
            load_to_staging(
                transform_sessions(valid_sessions), "website_sessions", engine
            )
            metrics.record(len(sessions), len(valid_sessions), len(rejected_sessions))
            step.record(len(valid_sessions))

        with track_pipeline_step(engine, run_id, "staging_pageviews") as step:
            loaded_before = metrics.rows_loaded
            process_pageview_chunks(engine, metrics, run_id)
            step.record(metrics.rows_loaded - loaded_before)

        with track_pipeline_step(engine, run_id, "staging_products") as step:
            products = extract_products(DATA_SOURCE_DIR / "products.json")
            valid_products, rejected_products = validate_products(products)
            logger.info(
                "products: valid=%s rejected=%s",
                len(valid_products),
                len(rejected_products),
            )
            quarantine_rejected_rows(
                rejected_products, "products", run_id, REJECTED_DIR
            )
            load_to_staging(transform_products(valid_products), "products", engine)
            metrics.record(len(products), len(valid_products), len(rejected_products))
            step.record(len(valid_products))

        with track_pipeline_step(engine, run_id, "staging_orders") as step:
            loaded_before = metrics.rows_loaded
            staged_order_ids = process_orders_incrementally(engine, metrics, run_id)
            step.record(metrics.rows_loaded - loaded_before)

        with track_pipeline_step(engine, run_id, "staging_order_items") as step:
            order_items = extract_order_items(engine)
            valid_items, rejected_items = validate_order_items(
                order_items, staged_order_ids, set(valid_products["product_id"])
            )
            logger.info(
                "order_items: valid=%s rejected=%s",
                len(valid_items),
                len(rejected_items),
            )
            quarantine_rejected_rows(
                rejected_items, "order_items", run_id, REJECTED_DIR
            )
            load_to_staging(transform_order_items(valid_items), "order_items", engine)
            metrics.record(len(order_items), len(valid_items), len(rejected_items))
            step.record(len(valid_items))

        with track_pipeline_step(engine, run_id, "staging_refunds") as step:
            refunds = extract_refunds(engine)
            valid_refunds, rejected_refunds = validate_refunds(
                refunds, set(valid_items["order_item_id"]), staged_order_ids
            )
            logger.info(
                "refunds: valid=%s rejected=%s",
                len(valid_refunds),
                len(rejected_refunds),
            )
            quarantine_rejected_rows(
                rejected_refunds, "order_item_refunds", run_id, REJECTED_DIR
            )
            load_to_staging(
                transform_refunds(valid_refunds), "order_item_refunds", engine
            )
            metrics.record(len(refunds), len(valid_refunds), len(rejected_refunds))
            step.record(len(valid_refunds))

        with track_pipeline_step(engine, run_id, "warehouse_et_marts") as step:
            # Le warehouse n'est déclaré prêt qu'après toutes les sources validées.
            warehouse_result = build_warehouse(engine)
            step.record(sum(warehouse_result.__dict__.values()))
            logger.info("WAREHOUSE READY run_id=%s volumes=%s", run_id, warehouse_result)

        finish_pipeline_run(engine, run_id, "SUCCESS", metrics)
        log_pipeline_summary(engine, run_id, "SUCCESS", metrics)
        logger.info(f"LOAD COMPLETED run_id={run_id}")
        return run_id
    except Exception as error:
        logger.exception(f"PIPELINE FAILED run_id={run_id}")
        try:
            finish_pipeline_run(engine, run_id, "FAILED", metrics, str(error))
            log_pipeline_summary(engine, run_id, "FAILED", metrics)
        except Exception:
            logger.exception(f"FAILED TO UPDATE PIPELINE RUN run_id={run_id}")
        raise


if __name__ == "__main__":
    run()
