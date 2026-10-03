from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.engine import Engine

MetricValue = int | Decimal


class WarehouseReconciliationError(RuntimeError):
    """Signale un écart entre les données du staging et du warehouse."""


@dataclass(frozen=True)
class ReconciliationCheck:
    """Résultat attendu et observé pour une règle de réconciliation."""

    name: str
    expected: MetricValue
    actual: MetricValue

    @property
    def passed(self) -> bool:
        """Indique si la mesure du warehouse correspond à sa source."""
        return self.expected == self.actual


@dataclass(frozen=True)
class ReconciliationReport:
    """Ensemble des contrôles exécutés après la construction du warehouse."""

    checks: tuple[ReconciliationCheck, ...]

    @property
    def passed(self) -> bool:
        """Indique si tous les contrôles sont réussis."""
        return all(check.passed for check in self.checks)


def reconcile_warehouse(engine: Engine) -> ReconciliationReport:
    """Compare les volumes et montants du staging avec les tables de faits.

    Les montants issus des colonnes flottantes du staging sont arrondis à deux
    décimales avant comparaison avec les valeurs ``NUMERIC`` du warehouse.
    """
    statement = text(
        """
        SELECT
            (SELECT COUNT(*) FROM staging.website_sessions) AS staging_sessions,
            (SELECT COUNT(*) FROM warehouse.fact_sessions) AS fact_sessions,
            (SELECT COUNT(*) FROM staging.website_pageviews) AS staging_pageviews,
            (SELECT COALESCE(SUM(pageview_count), 0)
             FROM warehouse.fact_sessions) AS fact_pageviews,
            (SELECT COUNT(*) FROM staging.orders) AS staging_orders,
            (SELECT COALESCE(SUM(order_count), 0)
             FROM warehouse.fact_sessions) AS fact_orders,
            (SELECT COUNT(*) FROM staging.order_items) AS staging_items,
            (SELECT COUNT(*) FROM warehouse.fact_sales) AS fact_items,
            (SELECT ROUND(COALESCE(SUM(price_usd), 0)::numeric, 2)
             FROM staging.order_items) AS staging_item_revenue,
            (SELECT COALESCE(SUM(price_usd), 0)
             FROM warehouse.fact_sales) AS fact_item_revenue,
            (SELECT ROUND(COALESCE(SUM(gross_profit), 0)::numeric, 2)
             FROM staging.order_items) AS staging_item_profit,
            (SELECT COALESCE(SUM(gross_profit_usd), 0)
             FROM warehouse.fact_sales) AS fact_item_profit,
            (SELECT ROUND(COALESCE(SUM(refund_amount_usd), 0)::numeric, 2)
             FROM staging.order_item_refunds) AS staging_refunds,
            (SELECT COALESCE(SUM(refund_amount_usd), 0)
             FROM warehouse.fact_sales) AS fact_refunds,
            (SELECT ROUND(COALESCE(SUM(price_usd), 0)::numeric, 2)
             FROM staging.orders) AS staging_order_revenue,
            (SELECT COALESCE(SUM(revenue_usd), 0)
             FROM warehouse.fact_sessions) AS fact_session_revenue,
            (SELECT ROUND(COALESCE(SUM(gross_profit), 0)::numeric, 2)
             FROM staging.orders) AS staging_order_profit,
            (SELECT COALESCE(SUM(gross_profit_usd), 0)
             FROM warehouse.fact_sessions) AS fact_session_profit
        """
    )
    with engine.connect() as connection:
        values = connection.execute(statement).mappings().one()

    pairs = (
        ("volume_sessions", "staging_sessions", "fact_sessions"),
        ("volume_pages_vues", "staging_pageviews", "fact_pageviews"),
        ("volume_commandes", "staging_orders", "fact_orders"),
        ("volume_articles", "staging_items", "fact_items"),
        ("ventes_articles", "staging_item_revenue", "fact_item_revenue"),
        ("marge_articles", "staging_item_profit", "fact_item_profit"),
        ("remboursements", "staging_refunds", "fact_refunds"),
        ("ventes_sessions", "staging_order_revenue", "fact_session_revenue"),
        ("marge_sessions", "staging_order_profit", "fact_session_profit"),
    )
    report = ReconciliationReport(
        checks=tuple(
            ReconciliationCheck(name, values[expected], values[actual])
            for name, expected, actual in pairs
        )
    )
    if not report.passed:
        failures = "; ".join(
            f"{check.name}: attendu={check.expected}, obtenu={check.actual}"
            for check in report.checks
            if not check.passed
        )
        raise WarehouseReconciliationError(
            f"Réconciliation du warehouse échouée : {failures}"
        )
    return report
