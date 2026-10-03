from unittest.mock import MagicMock

from src.marts.product_performance import build_product_performance


def test_build_product_performance_uses_one_transaction():
    """La création et le chargement du mart sont atomiques."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    connection.execute.return_value.rowcount = 4

    affected_rows = build_product_performance(engine)

    assert affected_rows == 4
    engine.begin.assert_called_once_with()
    assert connection.execute.call_count == 3


def test_build_product_performance_keeps_unsold_products():
    """La dimension pilote la jointure pour conserver tout le catalogue."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    build_product_performance(engine)

    statement = str(connection.execute.call_args_list[2].args[0])
    assert "FROM warehouse.dim_product AS p" in statement
    assert "LEFT JOIN sales_by_product AS s" in statement
    assert "COALESCE(s.units_sold, 0)" in statement


def test_build_product_performance_calculates_commercial_kpis():
    """Le mart calcule marge, remboursements et ventes additionnelles."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    build_product_performance(engine)

    statement = str(connection.execute.call_args_list[2].args[0])
    assert "gross_revenue_usd - refund_amount_usd" in statement
    assert "gross_profit_usd - refund_amount_usd" in statement
    assert "refunded_items::numeric / NULLIF(units_sold, 0)" in statement
    assert "secondary_items::numeric / NULLIF(units_sold, 0)" in statement
    assert "ON CONFLICT (product_key)" in statement
