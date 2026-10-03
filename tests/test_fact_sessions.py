from unittest.mock import MagicMock

from src.warehouse.fact_sessions import build_fact_sessions


def test_build_fact_sessions_uses_one_transaction():
    """La création et le chargement des faits sont atomiques."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    connection.execute.return_value.rowcount = 472_871

    affected_rows = build_fact_sessions(engine)

    assert affected_rows == 472_871
    engine.begin.assert_called_once_with()
    assert connection.execute.call_count == 3


def test_build_fact_sessions_aggregates_before_joining():
    """Pages et commandes sont agrégées sans multiplier les mesures."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    build_fact_sessions(engine)

    statement = str(connection.execute.call_args_list[2].args[0])
    assert "pageviews_by_session AS" in statement
    assert "orders_by_session AS" in statement
    assert statement.count("GROUP BY website_session_id") == 2


def test_build_fact_sessions_resolves_all_dimension_keys():
    """Chaque session est reliée aux quatre dimensions analytiques."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    build_fact_sessions(engine)

    statement = str(connection.execute.call_args_list[2].args[0])
    assert "JOIN warehouse.dim_customer" in statement
    assert "JOIN warehouse.dim_marketing" in statement
    assert "JOIN warehouse.dim_device" in statement
    assert "TO_CHAR(s.created_at, 'YYYYMMDD')::integer" in statement


def test_build_fact_sessions_calculates_behavior_metrics():
    """Le chargement calcule rebond, conversion et pages de parcours."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    build_fact_sessions(engine)

    statement = str(connection.execute.call_args_list[2].args[0])
    assert "p.pageview_count = 1" in statement
    assert "o.website_session_id IS NOT NULL" in statement
    assert "landing_page_url" in statement
    assert "exit_page_url" in statement
    assert "ON CONFLICT (website_session_id)" in statement
