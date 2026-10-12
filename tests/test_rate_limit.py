from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest
from ebird.api.requests import RateLimitError, get_rate_limit, set_rate_limit

from ebird.api.data.loaders import RATE_LIMIT, APILoader


@pytest.fixture(autouse=True)
def reset_rate_limit():
    yield
    set_rate_limit(0)


@pytest.fixture()
def loader():
    return APILoader("key", {"en": "en"}, wait=1)


def make_error(code):
    return HTTPError("http://example.com", code, "Error", None, BytesIO(b""))


def test_default_rate_limit(loader):
    assert get_rate_limit() == RATE_LIMIT


def test_set_rate_limit():
    APILoader("key", {"en": "en"}, rate_limit=2.5)
    assert get_rate_limit() == 2.5


def test_zero_disables_rate_limit():
    loader = APILoader("key", {"en": "en"}, rate_limit=0)
    assert loader.rate_limit == 0
    assert get_rate_limit() == 0


@patch("ebird.api.data.loaders.time.sleep")
def test_rate_limit_error_is_not_retried(mock_sleep, loader):
    func = MagicMock(side_effect=RateLimitError(make_error(429), 30.0))
    with pytest.raises(RateLimitError):
        loader.call(func)
    assert func.call_count == 1
    assert loader.retries == 0
    mock_sleep.assert_not_called()


@patch("ebird.api.data.loaders.time.sleep")
def test_http_errors_are_not_retried(mock_sleep, loader):
    func = MagicMock(side_effect=make_error(500))
    with pytest.raises(HTTPError):
        loader.call(func)
    assert func.call_count == 1
    assert loader.retries == 0
    mock_sleep.assert_not_called()


@patch("ebird.api.data.loaders.time.sleep")
def test_connection_errors_are_retried(mock_sleep, loader):
    func = MagicMock(side_effect=[URLError("timeout"), "ok"])
    assert loader.call(func) == "ok"
    assert loader.retries == 1


@patch("ebird.api.data.loaders.time.sleep")
def test_timeouts_are_retried(mock_sleep, loader):
    func = MagicMock(side_effect=[TimeoutError(), "ok"])
    assert loader.call(func) == "ok"
    assert loader.retries == 1
