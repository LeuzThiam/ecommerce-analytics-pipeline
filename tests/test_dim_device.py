from unittest.mock import MagicMock

from src.warehouse.dim_device import build_dim_device


def test_build_dim_device_uses_one_transaction():
    """La création et le chargement sont regroupés dans une transaction."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    connection.execute.return_value.rowcount = 2

    affected_rows = build_dim_device(engine)

    assert affected_rows == 2
    engine.begin.assert_called_once_with()
    assert connection.execute.call_count == 3


def test_build_dim_device_adds_business_attributes():
    """Le code technique reçoit un libellé français et un indicateur mobile."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    build_dim_device(engine)

    statement = str(connection.execute.call_args_list[2].args[0])
    assert "WHEN 'desktop' THEN 'ordinateur'" in statement
    assert "WHEN 'mobile' THEN 'mobile'" in statement
    assert "device_type = 'mobile'" in statement


def test_build_dim_device_is_idempotent_on_device_type():
    """Le type source est la clé métier utilisée pour éviter les doublons."""
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    build_dim_device(engine)

    create_statement = str(connection.execute.call_args_list[1].args[0])
    load_statement = str(connection.execute.call_args_list[2].args[0])
    assert "device_key INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY" in create_statement
    assert "device_type VARCHAR(50) NOT NULL UNIQUE" in create_statement
    assert "ON CONFLICT (device_type)" in load_statement
