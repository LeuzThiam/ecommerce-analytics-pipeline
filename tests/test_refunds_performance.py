from unittest.mock import MagicMock

from src.marts.refunds_performance import build_refunds_performance


def test_build_refunds_performance_uses_one_transaction():
    """La création et le chargement du mart sont atomiques."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    connection.execute.return_value.rowcount = 4

    affected_rows = build_refunds_performance(engine)

    assert affected_rows == 4
    engine.begin.assert_called_once_with()
    assert connection.execute.call_count == 3


def test_build_refunds_performance_uses_effective_refund_dates():
    """Les bornes temporelles viennent de la date réelle du remboursement."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    build_refunds_performance(engine)

    statement = str(connection.execute.call_args_list[2].args[0])
    assert "ON d.date_key = v.refund_date_key" in statement
    assert "MIN(d.date) AS first_refund_date" in statement
    assert "MAX(d.date) AS last_refund_date" in statement
    assert "WHERE v.is_refunded" in statement


def test_build_refunds_performance_calculates_risk_kpis():
    """Le mart compare fréquence et poids financier des remboursements."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    build_refunds_performance(engine)

    statement = str(connection.execute.call_args_list[2].args[0])
    assert "refund_amount_usd / NULLIF(items_refunded, 0)" in statement
    assert "items_refunded::numeric / NULLIF(items_sold, 0)" in statement
    assert "refund_amount_usd / NULLIF(gross_revenue_usd, 0)" in statement
    assert "gross_revenue_usd - refund_amount_usd" in statement
    assert "ON CONFLICT (product_key)" in statement
