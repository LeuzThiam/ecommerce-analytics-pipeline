from unittest.mock import MagicMock

from src.warehouse.dim_customer import build_dim_customer


def test_build_dim_customer_uses_one_transaction():
    """La table et ses données doivent être produites atomiquement."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    connection.execute.return_value.rowcount = 12

    affected_rows = build_dim_customer(engine)

    assert affected_rows == 12
    engine.begin.assert_called_once_with()
    assert connection.execute.call_count == 3


def test_build_dim_customer_aggregates_sessions_and_orders():
    """Les attributs client proviennent des deux sources comportementales."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    build_dim_customer(engine)

    load_statement = str(connection.execute.call_args_list[2].args[0])
    assert "FROM staging.website_sessions" in load_statement
    assert "FROM staging.orders" in load_statement
    assert "FULL OUTER JOIN order_customers" in load_statement
    assert "MIN(created_at) AS first_order_at" in load_statement
    assert "BOOL_OR(is_repeat_session = 1)" in load_statement


def test_build_dim_customer_is_idempotent_on_user_id():
    """L'identifiant métier pilote l'UPSERT sans recréer le client."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    build_dim_customer(engine)

    create_statement = str(connection.execute.call_args_list[1].args[0])
    load_statement = str(connection.execute.call_args_list[2].args[0])
    assert "customer_key INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY" in create_statement
    assert "user_id BIGINT NOT NULL UNIQUE" in create_statement
    assert "ON CONFLICT (user_id)" in load_statement
