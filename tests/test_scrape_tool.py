"""Tests for tool/scripts/scrape.py."""

import urllib.error
from unittest.mock import MagicMock, patch

from tool.scripts.scrape import run, SCHEMA


def test_schema_shape():
    assert SCHEMA["type"] == "function"
    fn = SCHEMA["function"]
    assert fn["name"] == "scrape_url"
    assert "url" in fn["parameters"]["properties"]
    assert "url" in fn["parameters"]["required"]


def _mock_response(html: str, encoding: str = "utf-8"):
    mock = MagicMock()
    mock.read.return_value = html.encode(encoding)
    mock.headers.get_content_charset.return_value = encoding
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    return mock


def test_strips_html_tags():
    html = "<html><body><p>Hello world</p></body></html>"
    with patch("urllib.request.urlopen", return_value=_mock_response(html)):
        result = run("http://example.com")
    assert "Hello world" in result
    assert "<p>" not in result


def test_strips_script_and_style_blocks():
    html = "<html><script>alert('x')</script><style>.a{}</style><p>Visible</p></html>"
    with patch("urllib.request.urlopen", return_value=_mock_response(html)):
        result = run("http://example.com")
    assert "alert" not in result
    assert ".a" not in result
    assert "Visible" in result


def test_truncates_to_max_chars():
    html = "<p>" + "a" * 10000 + "</p>"
    with patch("urllib.request.urlopen", return_value=_mock_response(html)):
        result = run("http://example.com", max_chars=500)
    assert len(result) <= 600  # truncation marker adds a little
    assert "truncated" in result


def test_url_error_returns_error_string():
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
        result = run("http://bad-host.invalid")
    assert result.startswith("error")
    assert "timeout" in result


def test_collapses_whitespace():
    html = "<p>Hello    \n\n  world</p>"
    with patch("urllib.request.urlopen", return_value=_mock_response(html)):
        result = run("http://example.com")
    assert "Hello world" in result
