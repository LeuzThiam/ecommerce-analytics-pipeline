from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from src.warehouse.build import WarehouseBuildResult, build_warehouse
from src.warehouse.dim_date import DateRange


def test_build_warehouse_respects_dependency_order():
    """Les dimensions doivent précéder les faits qui portent leurs clés."""
    engine = MagicMock()
    calls = []

    with (
        patch(
            "src.warehouse.build.build_dim_date_from_staging",
            side_effect=lambda _: (
                calls.append("dim_date")
                or (DateRange(date(2020, 1, 1), date(2020, 1, 2)), 2)
            ),
        ),
        patch(
            "src.warehouse.build.build_dim_product",
            side_effect=lambda _: calls.append("dim_product") or 4,
        ),
        patch(
            "src.warehouse.build.build_dim_customer",
            side_effect=lambda _: calls.append("dim_customer") or 100,
        ),
        patch(
            "src.warehouse.build.build_dim_marketing",
            side_effect=lambda _: calls.append("dim_marketing") or 9,
        ),
        patch(
            "src.warehouse.build.build_dim_device",
            side_effect=lambda _: calls.append("dim_device") or 2,
        ),
        patch(
            "src.warehouse.build.build_fact_sales",
            side_effect=lambda _: calls.append("fact_sales") or 40,
        ),
        patch(
            "src.warehouse.build.build_fact_sessions",
            side_effect=lambda _: calls.append("fact_sessions") or 500,
        ),
        patch(
            "src.warehouse.build.reconcile_warehouse",
            side_effect=lambda _: calls.append("reconciliation") or MagicMock(),
        ),
        patch(
            "src.warehouse.build.build_daily_performance",
            side_effect=lambda _: calls.append("daily_performance") or 1_109,
        ),
    ):
        result = build_warehouse(engine)

    assert calls == [
        "dim_date",
        "dim_product",
        "dim_customer",
        "dim_marketing",
        "dim_device",
        "fact_sales",
        "fact_sessions",
        "reconciliation",
        "daily_performance",
    ]
    assert result == WarehouseBuildResult(2, 4, 100, 9, 2, 40, 500, 1_109)


def test_build_warehouse_stops_when_a_dimension_fails():
    """Un fait ne doit jamais être reconstruit avec des dimensions incomplètes."""
    engine = MagicMock()

    with (
        patch(
            "src.warehouse.build.build_dim_date_from_staging",
            return_value=(DateRange(date(2020, 1, 1), date(2020, 1, 2)), 2),
        ),
        patch(
            "src.warehouse.build.build_dim_product",
            side_effect=RuntimeError("catalogue indisponible"),
        ),
        patch("src.warehouse.build.build_fact_sales") as mock_fact_sales,
        patch("src.warehouse.build.build_fact_sessions") as mock_fact_sessions,
    ):
        with pytest.raises(RuntimeError, match="catalogue indisponible"):
            build_warehouse(engine)

    mock_fact_sales.assert_not_called()
    mock_fact_sessions.assert_not_called()
