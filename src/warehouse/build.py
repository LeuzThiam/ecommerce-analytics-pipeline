import logging
from dataclasses import dataclass

from sqlalchemy.engine import Engine

from src.marts.daily_performance import build_daily_performance
from src.marts.marketing_performance import build_marketing_performance
from src.marts.product_performance import build_product_performance
from src.warehouse.dim_customer import build_dim_customer
from src.warehouse.dim_date import build_dim_date_from_staging
from src.warehouse.dim_device import build_dim_device
from src.warehouse.dim_marketing import build_dim_marketing
from src.warehouse.dim_product import build_dim_product
from src.warehouse.fact_sales import build_fact_sales
from src.warehouse.fact_sessions import build_fact_sessions
from src.warehouse.reconciliation import reconcile_warehouse

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WarehouseBuildResult:
    """Volumes affectés par chaque étape de construction du warehouse."""

    dim_date: int
    dim_product: int
    dim_customer: int
    dim_marketing: int
    dim_device: int
    fact_sales: int
    fact_sessions: int
    daily_performance: int
    marketing_performance: int
    product_performance: int


def build_warehouse(engine: Engine) -> WarehouseBuildResult:
    """Construit le schéma en étoile dans son ordre de dépendance.

    Les dimensions sont toujours chargées avant les faits qui référencent
    leurs clés. Chaque constructeur reste responsable de sa transaction, ce
    qui limite la durée des verrous sur les tables volumineuses.
    """
    logger.info("WAREHOUSE BUILD STARTED")

    _, dim_date_rows = build_dim_date_from_staging(engine)
    dim_product_rows = build_dim_product(engine)
    dim_customer_rows = build_dim_customer(engine)
    dim_marketing_rows = build_dim_marketing(engine)
    dim_device_rows = build_dim_device(engine)
    fact_sales_rows = build_fact_sales(engine)
    fact_sessions_rows = build_fact_sessions(engine)
    reconciliation = reconcile_warehouse(engine)
    daily_performance_rows = build_daily_performance(engine)
    marketing_performance_rows = build_marketing_performance(engine)
    product_performance_rows = build_product_performance(engine)

    result = WarehouseBuildResult(
        dim_date=dim_date_rows,
        dim_product=dim_product_rows,
        dim_customer=dim_customer_rows,
        dim_marketing=dim_marketing_rows,
        dim_device=dim_device_rows,
        fact_sales=fact_sales_rows,
        fact_sessions=fact_sessions_rows,
        daily_performance=daily_performance_rows,
        marketing_performance=marketing_performance_rows,
        product_performance=product_performance_rows,
    )
    logger.info("WAREHOUSE RECONCILIATION checks=%s", reconciliation.checks)
    logger.info("WAREHOUSE BUILD COMPLETED volumes=%s", result)
    return result
