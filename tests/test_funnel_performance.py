from unittest.mock import MagicMock

from src.marts.funnel_performance import build_funnel_performance


def test_build_funnel_performance_uses_one_transaction():
    """La création et le chargement du funnel sont atomiques."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    connection.execute.return_value.rowcount = 1_109

    affected_rows = build_funnel_performance(engine)

    assert affected_rows == 1_109
    engine.begin.assert_called_once_with()
    assert connection.execute.call_count == 3


def test_build_funnel_performance_deduplicates_each_session():
    """Chaque étape est réduite à un booléen avant l'agrégation quotidienne."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    build_funnel_performance(engine)

    statement = str(connection.execute.call_args_list[2].args[0])
    assert "page_steps_by_session AS" in statement
    assert "BOOL_OR(pageview_url = '/products')" in statement
    assert "GROUP BY website_session_id" in statement
    assert "WHERE s.is_converted" in statement


def test_build_funnel_performance_calculates_step_rates():
    """Chaque taux utilise comme dénominateur l'étape précédente."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    build_funnel_performance(engine)

    statement = str(connection.execute.call_args_list[2].args[0])
    assert "product_detail_sessions, 0)" in statement
    assert "shipping_sessions, 0)" in statement
    assert "billing_sessions, 0)" in statement
    assert "order_sessions::numeric / NULLIF(sessions, 0)" in statement
    assert "ON CONFLICT (date_key)" in statement
