from unittest.mock import MagicMock

from src.marts.marketing_performance import build_marketing_performance


def test_build_marketing_performance_uses_one_transaction():
    """La création et le chargement du mart sont atomiques."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    connection.execute.return_value.rowcount = 9

    affected_rows = build_marketing_performance(engine)

    assert affected_rows == 9
    engine.begin.assert_called_once_with()
    assert connection.execute.call_count == 3


def test_build_marketing_performance_keeps_grains_separate():
    """Les faits de sessions et de ventes sont agrégés avant leur jointure."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    build_marketing_performance(engine)

    statement = str(connection.execute.call_args_list[2].args[0])
    assert "sessions_by_marketing AS" in statement
    assert "sales_by_marketing AS" in statement
    assert "JOIN warehouse.fact_sessions AS s USING (website_session_id)" in statement
    assert statement.count("GROUP BY") == 2


def test_build_marketing_performance_calculates_profitability_kpis():
    """Le mart calcule ratios marketing et rentabilité après remboursement."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    build_marketing_performance(engine)

    statement = str(connection.execute.call_args_list[2].args[0])
    assert "gross_revenue_usd - refund_amount_usd" in statement
    assert "gross_profit_usd - refund_amount_usd" in statement
    assert "converted_sessions::numeric / NULLIF(sessions, 0)" in statement
    assert "gross_revenue_usd / NULLIF(sessions, 0)" in statement
    assert "ON CONFLICT (marketing_key)" in statement
