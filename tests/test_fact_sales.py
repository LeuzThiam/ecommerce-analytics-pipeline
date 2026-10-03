from unittest.mock import MagicMock

from src.warehouse.fact_sales import build_fact_sales


def test_build_fact_sales_uses_one_transaction():
    """La création et le chargement de la table de faits sont atomiques."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    connection.execute.return_value.rowcount = 40_025

    affected_rows = build_fact_sales(engine)

    assert affected_rows == 40_025
    engine.begin.assert_called_once_with()
    assert connection.execute.call_count == 3


def test_build_fact_sales_preserves_order_item_grain():
    """Les remboursements sont agrégés avant la jointure aux articles."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    build_fact_sales(engine)

    statement = str(connection.execute.call_args_list[2].args[0])
    assert "GROUP BY order_item_id" in statement
    assert "LEFT JOIN refunds_by_item" in statement
    assert "ON CONFLICT (order_item_id)" in statement


def test_build_fact_sales_resolves_dimension_keys():
    """Chaque vente est reliée aux dimensions date, produit et client."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    build_fact_sales(engine)

    statement = str(connection.execute.call_args_list[2].args[0])
    assert "JOIN warehouse.dim_product" in statement
    assert "JOIN warehouse.dim_customer" in statement
    assert "TO_CHAR(i.created_at, 'YYYYMMDD')::integer" in statement


def test_build_fact_sales_calculates_net_measures():
    """Les mesures nettes déduisent les remboursements du brut."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    build_fact_sales(engine)

    statement = str(connection.execute.call_args_list[2].args[0])
    assert "i.price_usd - COALESCE(r.refund_amount_usd, 0)" in statement
    assert "i.gross_profit - COALESCE(r.refund_amount_usd, 0)" in statement
    assert "r.order_item_id IS NOT NULL" in statement
