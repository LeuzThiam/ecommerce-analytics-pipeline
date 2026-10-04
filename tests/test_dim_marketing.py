from unittest.mock import MagicMock

from src.warehouse.dim_marketing import build_dim_marketing


def test_build_dim_marketing_uses_one_transaction():
    """La création et le peuplement de la dimension sont atomiques."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    connection.execute.return_value.rowcount = 9

    affected_rows = build_dim_marketing(engine)

    assert affected_rows == 9
    engine.begin.assert_called_once_with()
    assert connection.execute.call_count == 3


def test_build_dim_marketing_normalizes_missing_values():
    """Les valeurs absentes deviennent des membres métier explicites."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    build_dim_marketing(engine)

    statement = str(connection.execute.call_args_list[2].args[0])
    assert "COALESCE(utm_source, '(non renseigné)')" in statement
    assert "COALESCE(utm_campaign, '(non renseignée)')" in statement
    assert "COALESCE(http_referer, '(aucun)')" in statement
    assert "utm_source IS NULL" in statement
    assert "http_referer IS NULL" in statement


def test_build_dim_marketing_uses_combination_as_business_key():
    """Une combinaison d'acquisition existante ne doit pas être dupliquée."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    build_dim_marketing(engine)

    create_statement = str(connection.execute.call_args_list[1].args[0])
    load_statement = str(connection.execute.call_args_list[2].args[0])
    assert "marketing_key INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY" in create_statement
    assert "UNIQUE (utm_source, utm_campaign, utm_content, http_referer)" in create_statement
    assert "ON CONFLICT" in load_statement
    assert "is_direct = EXCLUDED.is_direct" in load_statement
