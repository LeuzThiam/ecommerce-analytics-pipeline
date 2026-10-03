from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.warehouse.reconciliation import (
    WarehouseReconciliationError,
    reconcile_warehouse,
)


def _reconciliation_values() -> dict:
    """Retourne un jeu cohérent couvrant tous les contrôles financiers."""
    return {
        "staging_sessions": 10,
        "fact_sessions": 10,
        "staging_pageviews": 25,
        "fact_pageviews": 25,
        "staging_orders": 3,
        "fact_orders": 3,
        "staging_items": 4,
        "fact_items": 4,
        "staging_item_revenue": Decimal("200.00"),
        "fact_item_revenue": Decimal("200.00"),
        "staging_item_profit": Decimal("120.00"),
        "fact_item_profit": Decimal("120.00"),
        "staging_refunds": Decimal("25.00"),
        "fact_refunds": Decimal("25.00"),
        "staging_order_revenue": Decimal("200.00"),
        "fact_session_revenue": Decimal("200.00"),
        "staging_order_profit": Decimal("120.00"),
        "fact_session_profit": Decimal("120.00"),
    }


def test_reconcile_warehouse_accepts_matching_metrics():
    """Un warehouse fidèle au staging produit neuf contrôles réussis."""
    engine = MagicMock()
    result = engine.connect.return_value.__enter__.return_value.execute.return_value
    result.mappings.return_value.one.return_value = _reconciliation_values()

    report = reconcile_warehouse(engine)

    assert report.passed
    assert len(report.checks) == 9
    assert all(check.passed for check in report.checks)


def test_reconcile_warehouse_reports_each_mismatch():
    """Le message d'erreur identifie la mesure divergente et ses valeurs."""
    engine = MagicMock()
    values = _reconciliation_values()
    values["fact_sessions"] = 9
    result = engine.connect.return_value.__enter__.return_value.execute.return_value
    result.mappings.return_value.one.return_value = values

    with pytest.raises(
        WarehouseReconciliationError,
        match="volume_sessions: attendu=10, obtenu=9",
    ):
        reconcile_warehouse(engine)
