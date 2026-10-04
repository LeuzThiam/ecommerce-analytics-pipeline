from unittest.mock import MagicMock

from src.warehouse.dim_product import build_dim_product


def test_build_dim_product_uses_one_transaction():
    """La création et le chargement partagent une transaction atomique."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    connection.execute.return_value.rowcount = 4

    affected_rows = build_dim_product(engine)

    assert affected_rows == 4
    engine.begin.assert_called_once_with()
    assert connection.execute.call_count == 3


def test_build_dim_product_uses_business_key_for_upsert():
    """Une nouvelle exécution doit mettre à jour le produit sans le doubler."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    build_dim_product(engine)

    load_statement = str(connection.execute.call_args_list[2].args[0])
    assert "FROM staging.products" in load_statement
    assert "ON CONFLICT (product_id)" in load_statement
    assert "product_name = EXCLUDED.product_name" in load_statement


def test_build_dim_product_creates_surrogate_key():
    """La dimension sépare la clé technique de l'identifiant source."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    build_dim_product(engine)

    create_statement = str(connection.execute.call_args_list[1].args[0])
    assert "product_key INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY" in create_statement
    assert "product_id INTEGER NOT NULL UNIQUE" in create_statement
