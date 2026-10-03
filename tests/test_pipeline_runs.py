from unittest.mock import MagicMock, patch

import pytest

from src.control.pipeline_runs import (
    PipelineRunMetrics,
    finish_pipeline_run,
    start_pipeline_run,
)


def test_metrics_accumulate_counts():
    metrics = PipelineRunMetrics()

    metrics.record(extracted=10, loaded=8, rejected=2)
    metrics.record(extracted=5, loaded=5, rejected=0)

    assert metrics.rows_extracted == 15
    assert metrics.rows_loaded == 13
    assert metrics.rows_rejected == 2


@patch("src.control.pipeline_runs.ensure_pipeline_runs_table")
@patch("src.control.pipeline_runs.uuid4")
def test_start_pipeline_run_creates_started_record(mock_uuid4, mock_ensure_table):
    mock_uuid4.return_value = "run-123"
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    run_id = start_pipeline_run(engine, pipeline_name="test_pipeline")

    assert run_id == "run-123"
    mock_ensure_table.assert_called_once_with(engine)
    parameters = connection.execute.call_args.args[1]
    assert parameters == {"run_id": "run-123", "pipeline_name": "test_pipeline"}


def test_finish_pipeline_run_updates_metrics():
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    metrics = PipelineRunMetrics(rows_extracted=20, rows_loaded=18, rows_rejected=2)

    finish_pipeline_run(engine, "run-123", "SUCCESS", metrics)

    parameters = connection.execute.call_args.args[1]
    assert parameters == {
        "run_id": "run-123",
        "status": "SUCCESS",
        "rows_extracted": 20,
        "rows_loaded": 18,
        "rows_rejected": 2,
        "error_message": None,
    }


def test_finish_pipeline_run_rejects_unknown_status():
    with pytest.raises(ValueError, match="Unsupported pipeline status"):
        finish_pipeline_run(
            MagicMock(),
            "run-123",
            "UNKNOWN",
            PipelineRunMetrics(),
        )
