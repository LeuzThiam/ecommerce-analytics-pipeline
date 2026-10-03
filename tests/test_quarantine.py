import pandas as pd
import pytest

from src.validation.quarantine import quarantine_rejected_rows


def test_empty_rejected_dataframe_creates_no_file(tmp_path):
    result = quarantine_rejected_rows(
        pd.DataFrame(),
        "orders",
        "run-123",
        tmp_path,
    )

    assert result is None
    assert list(tmp_path.iterdir()) == []


def test_rejected_rows_include_run_metadata(tmp_path):
    rejected = pd.DataFrame(
        [{"order_id": 10, "price_usd": -1.0}]
    )

    output_path = quarantine_rejected_rows(
        rejected,
        "orders",
        "run-123",
        tmp_path,
    )

    saved = pd.read_csv(output_path)
    assert output_path.name == "orders_run-123.csv"
    assert saved["order_id"].tolist() == [10]
    assert saved["_pipeline_run_id"].tolist() == ["run-123"]
    assert saved["_rejected_at"].notna().all()


def test_successive_chunks_are_appended_without_duplicate_header(tmp_path):
    first_chunk = pd.DataFrame([{"website_pageview_id": 1}])
    second_chunk = pd.DataFrame([{"website_pageview_id": 2}])

    output_path = quarantine_rejected_rows(
        first_chunk,
        "website_pageviews",
        "run-123",
        tmp_path,
    )
    quarantine_rejected_rows(
        second_chunk,
        "website_pageviews",
        "run-123",
        tmp_path,
    )

    saved = pd.read_csv(output_path)
    assert saved["website_pageview_id"].tolist() == [1, 2]
    assert output_path.read_text(encoding="utf-8").count("_pipeline_run_id") == 1


@pytest.mark.parametrize(
    ("source_name", "run_id"),
    [
        ("../orders", "run-123"),
        ("orders", "../run-123"),
        ("orders/invalid", "run-123"),
    ],
)
def test_quarantine_rejects_unsafe_filename_parts(
    source_name,
    run_id,
    tmp_path,
):
    with pytest.raises(ValueError, match="Invalid"):
        quarantine_rejected_rows(
            pd.DataFrame([{"id": 1}]),
            source_name,
            run_id,
            tmp_path,
        )
