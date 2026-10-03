from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.control.pipeline_runs import PipelineRunMetrics
from src.extract.csv_extractor import iter_pageview_chunks
from src.main import process_pageview_chunks


def test_iter_pageview_chunks_reads_file_in_configured_batches(tmp_path):
    path = tmp_path / "pageviews.csv"
    pd.DataFrame(
        {
            "website_pageview_id": [1, 2, 3, 4, 5],
            "website_session_id": [11, 12, 13, 14, 15],
            "created_at": ["2026-01-01 10:00:00"] * 5,
            "pageview_url": ["/home"] * 5,
        }
    ).to_csv(path, index=False)

    chunks = list(iter_pageview_chunks(path, chunk_size=2))

    assert [len(chunk) for chunk in chunks] == [2, 2, 1]
    assert pd.concat(chunks)["website_pageview_id"].tolist() == [1, 2, 3, 4, 5]


def test_iter_pageview_chunks_rejects_invalid_size(tmp_path):
    with pytest.raises(ValueError, match="greater than zero"):
        list(iter_pageview_chunks(tmp_path / "pageviews.csv", chunk_size=0))


@patch("src.main.load_to_staging")
@patch("src.main.quarantine_rejected_rows")
@patch("src.main.iter_pageview_chunks")
def test_process_pageview_chunks_replaces_then_appends(
    mock_chunks,
    mock_quarantine,
    mock_load,
):
    mock_chunks.return_value = iter(
        [
            pd.DataFrame(
                {
                    "website_pageview_id": [1, 2],
                    "website_session_id": [11, 12],
                    "created_at": ["2026-01-01 10:00:00"] * 2,
                    "pageview_url": ["/home", "/products"],
                }
            ),
            pd.DataFrame(
                {
                    "website_pageview_id": [3],
                    "website_session_id": [13],
                    "created_at": ["2026-01-01 10:05:00"],
                    "pageview_url": ["/cart"],
                }
            ),
        ]
    )
    engine = MagicMock()
    metrics = PipelineRunMetrics()

    process_pageview_chunks(engine, metrics, "run-123")

    assert mock_load.call_count == 2
    assert mock_load.call_args_list[0].kwargs["if_exists"] == "replace"
    assert mock_load.call_args_list[1].kwargs["if_exists"] == "append"
    assert metrics.rows_extracted == 3
    assert metrics.rows_loaded == 3
    assert metrics.rows_rejected == 0
    assert mock_quarantine.call_count == 2
