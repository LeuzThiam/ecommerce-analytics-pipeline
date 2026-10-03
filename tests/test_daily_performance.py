from unittest.mock import MagicMock

from src.marts.daily_performance import build_daily_performance


def test_build_daily_performance_uses_one_transaction():
    """La création et le chargement du mart sont atomiques."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    connection.execute.return_value.rowcount = 1_109

    affected_rows = build_daily_performance(engine)

    assert affected_rows == 1_109
    engine.begin.assert_called_once_with()
    assert connection.execute.call_count == 3


def test_build_daily_performance_aggregates_each_grain_separately():
    """Les agrégats indépendants évitent de multiplier sessions et ventes."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    build_daily_performance(engine)

    statement = str(connection.execute.call_args_list[2].args[0])
    assert "sessions_by_date AS" in statement
    assert "sales_by_date AS" in statement
    assert "refunds_by_date AS" in statement
    assert "GROUP BY refund_date_key" in statement


def test_build_daily_performance_calculates_business_kpis():
    """Le mart expose les ratios et les mesures financières nettes."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    build_daily_performance(engine)

    statement = str(connection.execute.call_args_list[2].args[0])
    assert "gross_revenue_usd - refund_amount_usd" in statement
    assert "gross_profit_usd - refund_amount_usd" in statement
    assert "converted_sessions::numeric / NULLIF(sessions, 0)" in statement
    assert "bounces::numeric / NULLIF(sessions, 0)" in statement
    assert "gross_revenue_usd / NULLIF(orders, 0)" in statement
    assert "ON CONFLICT (date_key)" in statement
