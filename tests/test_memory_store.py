"""Tests for memory/store.py — session persistence and lookup."""

import pytest

from memory import store


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "_DB_PATH", tmp_path / "test.db")
    store.init_db()


def _msgs(*users):
    out = [{"role": "system", "content": "sys"}]
    for u in users:
        out.append({"role": "user", "content": u})
        out.append({"role": "assistant", "content": "ok"})
    return out


def test_get_session_returns_metadata(db):
    store.save_session("s1", _msgs("hi"), "qwen3:8b", "2026-07-20", "checkout")
    meta = store.get_session("s1")
    assert meta["id"] == "s1"
    assert meta["project"] == "checkout"
    assert meta["date"] == "2026-07-20"
    assert meta["turn_count"] == 1


def test_get_session_missing_returns_none(db):
    assert store.get_session("nope") is None


def test_get_session_preserves_null_project(db):
    store.save_session("s1", _msgs("hi"), "qwen3:8b", "2026-07-20", None)
    assert store.get_session("s1")["project"] is None


def test_resume_keeps_project_attached(db):
    """The /resume bug: re-saving under the same id must not orphan the project."""
    store.save_session("s1", _msgs("first"), "qwen3:8b", "2026-07-20", "checkout")

    meta = store.get_session("s1")
    messages = store.load_session("s1")
    messages.append({"role": "user", "content": "second"})
    store.save_session("s1", messages, "qwen3:8b", meta["date"], meta["project"])

    after = store.get_session("s1")
    assert after["project"] == "checkout"
    assert after["turn_count"] == 2
    assert len(store.list_sessions()) == 1  # continued, not forked


def test_save_session_replaces_messages(db):
    store.save_session("s1", _msgs("a"), "qwen3:8b", "2026-07-20", "p")
    store.save_session("s1", _msgs("a", "b"), "qwen3:8b", "2026-07-20", "p")
    assert len(store.load_session("s1")) == 5


def test_register_then_save_keeps_one_row(db):
    store.register_session("s1", "2026-07-20", "p", "qwen3:8b")
    store.save_session("s1", _msgs("hi"), "qwen3:8b", "2026-07-20", "p")
    assert len(store.list_sessions()) == 1


def test_find_session_matches_date_and_project(db):
    store.register_session("a", "2026-07-20", "alpha", "qwen3:8b")
    store.register_session("b", "2026-07-20", "beta", "qwen3:8b")
    assert store.find_session("2026-07-20", "alpha")["id"] == "a"
    assert store.find_session("2026-07-20", "gamma") is None
    assert store.find_session("2026-07-21", "alpha") is None


def test_load_project_history_is_chronological(db):
    store.save_session("late", _msgs("second"), "qwen3:8b", "2026-07-25", "p")
    store.save_session("early", _msgs("first"), "qwen3:8b", "2026-07-20", "p")
    history = store.load_project_history("p")
    assert [h["id"] for h in history] == ["early", "late"]


def test_load_project_history_skips_empty_sessions(db):
    store.register_session("empty", "2026-07-20", "p", "qwen3:8b")
    store.save_session("real", _msgs("hi"), "qwen3:8b", "2026-07-21", "p")
    assert [h["id"] for h in store.load_project_history("p")] == ["real"]


def test_load_project_history_scopes_to_project(db):
    store.save_session("mine", _msgs("hi"), "qwen3:8b", "2026-07-20", "alpha")
    store.save_session("theirs", _msgs("hi"), "qwen3:8b", "2026-07-20", "beta")
    assert [h["id"] for h in store.load_project_history("alpha")] == ["mine"]
