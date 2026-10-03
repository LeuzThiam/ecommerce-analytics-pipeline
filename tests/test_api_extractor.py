from datetime import datetime
from unittest.mock import MagicMock, call, patch

import pytest
import requests

from src.extract.api_extractor import ORDER_COLUMNS, extract_orders


def make_response(total, orders):
    response = MagicMock()
    response.json.return_value = {"total": total, "orders": orders}
    return response


@patch("src.extract.api_extractor.requests.get")
def test_extract_orders_paginates_with_received_row_count(mock_get):
    mock_get.side_effect = [
        make_response(3, [{"order_id": 1}, {"order_id": 2}]),
        make_response(3, [{"order_id": 3}]),
    ]

    result = extract_orders("http://localhost:8000", page_size=2)

    assert result["order_id"].tolist() == [1, 2, 3]
    assert mock_get.call_args_list == [
        call(
            "http://localhost:8000/orders",
            params={"limit": 2, "offset": 0},
            timeout=30,
        ),
        call(
            "http://localhost:8000/orders",
            params={"limit": 2, "offset": 2},
            timeout=30,
        ),
    ]


@patch("src.extract.api_extractor.requests.get")
def test_extract_orders_sends_checkpoint_parameters(mock_get):
    mock_get.return_value = make_response(0, [])
    checkpoint_date = datetime(2026, 1, 1, 10, 0)

    extract_orders(
        "http://localhost:8000",
        created_after=checkpoint_date,
        after_id=42,
    )

    mock_get.assert_called_once_with(
        "http://localhost:8000/orders",
        params={
            "limit": 1000,
            "offset": 0,
            "created_after": "2026-01-01T10:00:00",
            "after_id": 42,
        },
        timeout=30,
    )


@patch("src.extract.api_extractor.requests.get")
def test_extract_orders_preserves_columns_when_no_rows(mock_get):
    mock_get.return_value = make_response(0, [])

    result = extract_orders("http://localhost:8000")

    assert result.empty
    assert result.columns.tolist() == ORDER_COLUMNS


def test_extract_orders_rejects_incomplete_checkpoint():
    with pytest.raises(ValueError, match="must be provided together"):
        extract_orders(
            "http://localhost:8000",
            created_after=datetime(2026, 1, 1, 10, 0),
        )


@patch("src.extract.api_extractor.time.sleep")
@patch("src.extract.api_extractor.requests.get")
def test_extract_orders_retries_after_timeout(mock_get, mock_sleep):
    mock_get.side_effect = [
        requests.Timeout("temporary timeout"),
        make_response(0, []),
    ]

    result = extract_orders("http://localhost:8000")

    assert result.empty
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once_with(1.0)


@patch("src.extract.api_extractor.time.sleep")
@patch("src.extract.api_extractor.requests.get")
def test_extract_orders_uses_exponential_backoff(mock_get, mock_sleep):
    server_error = requests.HTTPError(response=MagicMock(status_code=503))
    mock_get.side_effect = [
        server_error,
        server_error,
        make_response(0, []),
    ]

    extract_orders("http://localhost:8000")

    assert mock_sleep.call_args_list == [call(1.0), call(2.0)]


@patch("src.extract.api_extractor.time.sleep")
@patch("src.extract.api_extractor.requests.get")
def test_extract_orders_does_not_retry_client_error(mock_get, mock_sleep):
    mock_get.side_effect = requests.HTTPError(
        response=MagicMock(status_code=400)
    )

    with pytest.raises(requests.HTTPError):
        extract_orders("http://localhost:8000")

    mock_get.assert_called_once()
    mock_sleep.assert_not_called()


@patch("src.extract.api_extractor.time.sleep")
@patch("src.extract.api_extractor.requests.get")
def test_extract_orders_stops_after_max_attempts(mock_get, mock_sleep):
    mock_get.side_effect = requests.ConnectionError("API unavailable")

    with pytest.raises(requests.ConnectionError):
        extract_orders(
            "http://localhost:8000",
            max_attempts=3,
            retry_delay_seconds=0,
        )

    assert mock_get.call_count == 3
    assert mock_sleep.call_count == 2


@pytest.mark.parametrize(
    ("max_attempts", "retry_delay_seconds", "message"),
    [
        (0, 1.0, "max_attempts"),
        (3, -1.0, "retry_delay_seconds"),
    ],
)
def test_extract_orders_rejects_invalid_retry_configuration(
    max_attempts,
    retry_delay_seconds,
    message,
):
    with pytest.raises(ValueError, match=message):
        extract_orders(
            "http://localhost:8000",
            max_attempts=max_attempts,
            retry_delay_seconds=retry_delay_seconds,
        )
