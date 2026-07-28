"""Tests for the /wiki source slash command."""

import pytest

import agent


class FakeSession:
    def __init__(self, project=None):
        self.project = project
        self.session_id = "sid"


def _session_row(sid, date, turns, messages):
    return {"id": sid, "date": date, "started_at": date, "turn_count": turns, "messages": messages}


@pytest.fixture
def history(monkeypatch):
    store = {}
    monkeypatch.setattr(agent, "load_project_history", lambda p: store.get(p, []))
    return store


@pytest.fixture
def tool_calls(monkeypatch):
    calls = []

    def fake_run_tool(name, args):
        calls.append((name, args))
        return "FULL TRANSCRIPT TEXT"

    monkeypatch.setattr(agent, "run_tool", fake_run_tool)
    return calls


def test_requires_active_project(capsys, history):
    agent._handle_wiki("source", [FakeSession(project=None)])
    out = capsys.readouterr().out
    assert "No active project" in out
    assert "/project <name>" in out


def test_reports_when_project_has_no_history(capsys, history):
    agent._handle_wiki("source", [FakeSession(project="empty")])
    assert "No recorded conversations for 'empty'" in capsys.readouterr().out


def test_summary_lists_sessions(capsys, history):
    history["p"] = [
        _session_row("s1", "2026-07-20", 1, [{"role": "user", "content": "first thing"}]),
        _session_row("s2", "2026-07-24", 2, [{"role": "user", "content": "second thing"}]),
    ]
    agent._handle_wiki("source", [FakeSession(project="p")])
    out = capsys.readouterr().out
    assert "2 session(s)" in out
    assert "s1" in out and "s2" in out
    assert "2026-07-20" in out
    assert "first thing" in out


def test_summary_preview_collapses_whitespace(capsys, history):
    history["p"] = [_session_row("s1", "2026-07-20", 1, [
        {"role": "user", "content": "line one\n\nline   two"},
    ])]
    agent._handle_wiki("source", [FakeSession(project="p")])
    assert "line one line two" in capsys.readouterr().out


def test_summary_handles_session_with_no_user_turn(capsys, history):
    history["p"] = [_session_row("s1", "2026-07-20", 0, [
        {"role": "assistant", "content": "orphan reply"},
    ])]
    agent._handle_wiki("source", [FakeSession(project="p")])
    assert "s1" in capsys.readouterr().out  # does not raise


def test_full_flag_routes_through_read_sessions(capsys, history, tool_calls):
    agent._handle_wiki("source --full", [FakeSession(project="p")])
    assert tool_calls == [("read_sessions", {"project": "p"})]
    assert "FULL TRANSCRIPT TEXT" in capsys.readouterr().out


def test_full_short_flag(capsys, history, tool_calls):
    agent._handle_wiki("source -f", [FakeSession(project="p")])
    assert tool_calls[0][0] == "read_sessions"


def test_full_flag_still_requires_project(capsys, history, tool_calls):
    agent._handle_wiki("source --full", [FakeSession(project=None)])
    assert tool_calls == []
    assert "No active project" in capsys.readouterr().out


def test_unknown_option_rejected(capsys, history, tool_calls):
    agent._handle_wiki("source --nope", [FakeSession(project="p")])
    out = capsys.readouterr().out
    assert "Unknown option" in out
    assert tool_calls == []


def test_bare_wiki_shows_help(capsys):
    agent._handle_wiki("", [FakeSession(project="p")])
    assert "/wiki source" in capsys.readouterr().out


def test_unknown_subcommand_shows_help(capsys):
    agent._handle_wiki("bogus", [FakeSession(project="p")])
    out = capsys.readouterr().out
    assert "Unknown wiki command 'bogus'" in out
    assert "/wiki source" in out


def test_wiki_listed_in_slash_help():
    assert "/wiki source" in agent.SLASH_HELP
