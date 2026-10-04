from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError

from src.control.pipeline_runs import PipelineRunMetrics
from src.extract.csv_extractor import extract_sessions
from src.extract.json_extractor import extract_products
from src.extract.sql_extractor import extract_order_items, extract_refunds
from src.main import run


def test_missing_csv_source_raises_clear_error(tmp_path):
    missing_path = tmp_path / "website_sessions.csv"

    with pytest.raises(FileNotFoundError):
        extract_sessions(missing_path)


def test_invalid_json_source_raises_clear_error(tmp_path):
    invalid_path = tmp_path / "products.json"
    invalid_path.write_text('{"product_id": 1,', encoding="utf-8")

    with pytest.raises(ValueError):
        extract_products(invalid_path)


@pytest.mark.parametrize(
    "extractor",
    [extract_order_items, extract_refunds],
)
def test_unavailable_postgres_source_propagates_database_error(
    extractor,
):
    engine = MagicMock()
    database_error = OperationalError(
        "SELECT 1",
        {},
        ConnectionError("PostgreSQL unavailable"),
    )

    with patch("pandas.read_sql", side_effect=database_error):
        with pytest.raises(OperationalError, match="PostgreSQL unavailable"):
            extractor(engine)


@patch("src.main.finish_pipeline_run")
@patch("src.main.extract_sessions")
@patch("src.main.start_pipeline_run")
@patch("src.main.create_engine")
def test_pipeline_records_failed_status_when_source_is_missing(
    mock_create_engine,
    mock_start_pipeline_run,
    mock_extract_sessions,
    mock_finish_pipeline_run,
):
    engine = MagicMock()
    mock_create_engine.return_value = engine
    mock_start_pipeline_run.return_value = "run-123"
    mock_extract_sessions.side_effect = FileNotFoundError(
        "website_sessions.csv is missing"
    )

    with pytest.raises(FileNotFoundError, match="website_sessions.csv is missing"):
        run()

    args = mock_finish_pipeline_run.call_args.args
    assert args[0] is engine
    assert args[1] == "run-123"
    assert args[2] == "FAILED"
    assert args[3] == PipelineRunMetrics()
    assert args[4] == "website_sessions.csv is missing"
