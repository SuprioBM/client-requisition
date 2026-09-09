from __future__ import annotations

import pytest

from app.core.exceptions import UnauthorizedError, WebsiteError
from app.core.security import validate_public_url, verify_api_key


def test_verify_api_key_ok():
    verify_api_key("test-key")  # matches conftest


def test_verify_api_key_bad():
    with pytest.raises(UnauthorizedError):
        verify_api_key("wrong")


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/",
        "http://127.0.0.1/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "ftp://example.com/",
        "file:///etc/passwd",
    ],
)
def test_validate_public_url_blocks_dangerous(url):
    with pytest.raises(WebsiteError):
        validate_public_url(url)


def test_validate_public_url_allows_public():
    assert validate_public_url("https://example.com/path") == "https://example.com/path"
