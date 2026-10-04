from unittest.mock import MagicMock, patch

import pytest

from src.control.pipeline_runs import (
    PipelineRunMetrics,
    finish_pipeline_run,
    get_pipeline_step_summaries,
    start_pipeline_run,
    track_pipeline_step,
)


def test_metrics_accumulate_counts():
    metrics = PipelineRunMetrics()

    metrics.record(extracted=10, loaded=8, rejected=2)
    metrics.record(extracted=5, loaded=5, rejected=0)

    assert metrics.rows_extracted == 15
    assert metrics.rows_loaded == 13
    assert metrics.rows_rejected == 2


@patch("src.control.pipeline_runs.ensure_pipeline_step_runs_table")
@patch("src.control.pipeline_runs.ensure_pipeline_runs_table")
@patch("src.control.pipeline_runs.uuid4")
def test_start_pipeline_run_creates_started_record(
    mock_uuid4,
    mock_ensure_run_table,
    mock_ensure_step_table,
):
    mock_uuid4.return_value = "run-123"
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value

    run_id = start_pipeline_run(engine, pipeline_name="test_pipeline")

    assert run_id == "run-123"
    mock_ensure_run_table.assert_called_once_with(engine)
    mock_ensure_step_table.assert_called_once_with(engine)
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


@patch("src.control.pipeline_runs.perf_counter", side_effect=[10.0, 11.2345])
def test_track_pipeline_step_records_success(mock_perf_counter):
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    connection.execute.return_value.scalar_one.return_value = 42

    with track_pipeline_step(engine, "run-123", "staging_sessions") as metrics:
        metrics.record(120)

    parameters = connection.execute.call_args.args[1]
    assert parameters == {
        "step_run_id": 42,
        "status": "SUCCESS",
        "duration_seconds": 1.235,
        "rows_processed": 120,
        "error_message": None,
    }


@patch("src.control.pipeline_runs.perf_counter", side_effect=[10.0, 10.5])
def test_track_pipeline_step_records_failure(mock_perf_counter):
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    connection.execute.return_value.scalar_one.return_value = 43

    with pytest.raises(RuntimeError, match="source indisponible"):
        with track_pipeline_step(engine, "run-123", "staging_orders"):
            raise RuntimeError("source indisponible")

    parameters = connection.execute.call_args.args[1]
    assert parameters["status"] == "FAILED"
    assert parameters["duration_seconds"] == 0.5
    assert parameters["error_message"] == "source indisponible"


def test_get_pipeline_step_summaries_preserves_execution_order():
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.mappings.return_value.all.return_value = [
        {
            "step_name": "staging_sessions",
            "status": "SUCCESS",
            "duration_seconds": 1.25,
            "rows_processed": 472_871,
        },
        {
            "step_name": "warehouse_et_marts",
            "status": "SUCCESS",
            "duration_seconds": 3.5,
            "rows_processed": 100,
        },
    ]

    summaries = get_pipeline_step_summaries(engine, "run-123")

    assert [summary.step_name for summary in summaries] == [
        "staging_sessions",
        "warehouse_et_marts",
    ]
    assert summaries[0].rows_processed == 472_871
