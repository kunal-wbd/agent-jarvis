"""Tests for the read_sessions stdio tool."""

import pytest

from tool.stdio import server


def _session(sid, date, messages):
    return {"id": sid, "date": date, "started_at": date, "turn_count": 1, "messages": messages}


@pytest.fixture
def history(monkeypatch):
    """Patch load_project_history so tests do not touch the real memory.db."""
    store = {}

    def fake_load(project):
        return store.get(project, [])

    monkeypatch.setattr(server, "load_project_history", fake_load)
    return store


def test_no_sessions_for_project(history):
    assert "No recorded conversations" in server._read_sessions("nope")


def test_renders_user_and_assistant(history):
    history["p"] = [_session("s1", "2026-07-20", [
        {"role": "user", "content": "Build checkout."},
        {"role": "assistant", "content": "Understood."},
    ])]
    out = server._read_sessions("p")
    assert "USER: Build checkout." in out
    assert "ASSISTANT: Understood." in out


def test_excludes_system_and_tool_turns(history):
    history["p"] = [_session("s1", "2026-07-20", [
        {"role": "system", "content": "SECRET PERSONA"},
        {"role": "user", "content": "hello"},
        {"role": "tool", "content": "wrote 1842 bytes"},
    ])]
    out = server._read_sessions("p")
    assert "SECRET PERSONA" not in out
    assert "1842 bytes" not in out
    assert "USER: hello" in out


def test_skips_sessions_with_no_usable_turns(history):
    history["p"] = [
        _session("empty", "2026-07-20", [{"role": "system", "content": "sys"}]),
        _session("real", "2026-07-21", [{"role": "user", "content": "hi"}]),
    ]
    out = server._read_sessions("p")
    assert "1 sessions" in out
    assert "empty" not in out


def test_skips_blank_content(history):
    history["p"] = [_session("s1", "2026-07-20", [
        {"role": "user", "content": "   "},
        {"role": "assistant", "content": "real answer"},
    ])]
    out = server._read_sessions("p")
    assert "USER:" not in out
    assert "real answer" in out


def test_all_blank_returns_no_content_message(history):
    history["p"] = [_session("s1", "2026-07-20", [{"role": "user", "content": ""}])]
    assert "No conversation content" in server._read_sessions("p")


def test_chronological_order(history):
    history["p"] = [
        _session("old", "2026-07-20", [{"role": "user", "content": "first"}]),
        _session("new", "2026-07-25", [{"role": "user", "content": "second"}]),
    ]
    out = server._read_sessions("p")
    assert out.index("first") < out.index("second")


def test_truncation_keeps_newest_session(history):
    history["p"] = [
        _session("old", "2026-07-20", [{"role": "user", "content": "x" * 300}]),
        _session("new", "2026-07-25", [{"role": "user", "content": "KEEPME"}]),
    ]
    out = server._read_sessions("p", max_chars=120)
    assert "KEEPME" in out
    assert "1 earlier session(s) omitted" in out


def test_long_message_is_truncated(history):
    history["p"] = [_session("s1", "2026-07-20", [
        {"role": "assistant", "content": "y" * (server._MAX_MSG_CHARS + 500)},
    ])]
    out = server._read_sessions("p")
    assert "[...truncated]" in out


def test_db_error_is_reported_not_raised(monkeypatch):
    def boom(project):
        raise RuntimeError("db locked")

    monkeypatch.setattr(server, "load_project_history", boom)
    assert "error reading sessions" in server._read_sessions("p")


def test_registered_in_tools():
    assert "read_sessions" in server._TOOLS
    schema = server._TOOLS["read_sessions"]["inputSchema"]
    assert schema["required"] == ["project"]
    assert "max_chars" in schema["properties"]
