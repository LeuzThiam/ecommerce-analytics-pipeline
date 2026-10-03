from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from src.warehouse.dim_date import (
    DateRange,
    build_dim_date,
    build_dim_date_from_staging,
    get_staging_date_range,
)


def test_get_staging_date_range_returns_global_boundaries():
    engine = MagicMock()
    result = engine.connect.return_value.__enter__.return_value.execute.return_value
    result.mappings.return_value.one.return_value = {
        "start_date": date(2012, 3, 19),
        "end_date": date(2015, 3, 19),
    }

    date_range = get_staging_date_range(engine)

    assert date_range == DateRange(date(2012, 3, 19), date(2015, 3, 19))


def test_get_staging_date_range_rejects_empty_staging():
    engine = MagicMock()
    result = engine.connect.return_value.__enter__.return_value.execute.return_value
    result.mappings.return_value.one.return_value = {
        "start_date": None,
        "end_date": None,
    }

    with pytest.raises(ValueError, match="empty staging"):
        get_staging_date_range(engine)


def test_build_dim_date_uses_one_transaction_and_expected_boundaries():
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    connection.execute.return_value.rowcount = 3

    affected_rows = build_dim_date(
        engine,
        date(2026, 1, 1),
        date(2026, 1, 3),
    )

    assert affected_rows == 3
    assert connection.execute.call_count == 3
    parameters = connection.execute.call_args.args[1]
    assert parameters == {
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 1, 3),
    }


def test_build_dim_date_rejects_reversed_boundaries():
    with pytest.raises(ValueError, match="start_date"):
        build_dim_date(
            MagicMock(),
            date(2026, 1, 2),
            date(2026, 1, 1),
        )


@patch("src.warehouse.dim_date.build_dim_date")
@patch("src.warehouse.dim_date.get_staging_date_range")
def test_build_dim_date_from_staging_orchestrates_steps(
    mock_get_range,
    mock_build,
):
    engine = MagicMock()
    expected_range = DateRange(date(2026, 1, 1), date(2026, 12, 31))
    mock_get_range.return_value = expected_range
    mock_build.return_value = 365

    date_range, affected_rows = build_dim_date_from_staging(engine)

    assert date_range == expected_range
    assert affected_rows == 365
    mock_build.assert_called_once_with(
        engine,
        expected_range.start_date,
        expected_range.end_date,
    )
