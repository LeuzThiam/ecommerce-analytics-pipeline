from unittest.mock import MagicMock

from src.marts.customer_summary import build_customer_summary


def test_build_customer_summary_uses_one_transaction():
    """La création et le chargement du mart sont atomiques."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    connection.execute.return_value.rowcount = 394_318

    affected_rows = build_customer_summary(engine)

    assert affected_rows == 394_318
    engine.begin.assert_called_once_with()
    assert connection.execute.call_count == 3


def test_build_customer_summary_keeps_prospects():
    """La dimension pilote les jointures pour conserver les non-acheteurs."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    build_customer_summary(engine)

    statement = str(connection.execute.call_args_list[2].args[0])
    assert "FROM warehouse.dim_customer AS c" in statement
    assert "LEFT JOIN sessions_by_customer AS s" in statement
    assert "LEFT JOIN sales_by_customer AS v" in statement
    assert "WHEN order_count = 0 THEN 'prospect'" in statement


def test_build_customer_summary_calculates_lifetime_metrics():
    """Le mart calcule valeur client, panier moyen et délai de conversion."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    build_customer_summary(engine)

    statement = str(connection.execute.call_args_list[2].args[0])
    assert "SUM(v.net_revenue_usd)" in statement
    assert "SUM(v.net_profit_usd)" in statement
    assert "gross_revenue_usd / NULLIF(order_count, 0)" in statement
    assert "first_order_at::date - first_session_at::date" in statement
    assert "order_count > 1" in statement
    assert "ON CONFLICT (customer_key)" in statement
