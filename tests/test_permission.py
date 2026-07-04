"""Tests for permission/permission.py."""

from permission.permission import check, SIDE_EFFECT_TOOLS


def test_read_file_auto_approved():
    assert check("read_file", {"path": "foo.txt"}) is True


def test_list_dir_auto_approved():
    assert check("list_dir", {"path": "."}) is True


def test_side_effect_tools_set():
    assert "write_file" in SIDE_EFFECT_TOOLS
    assert "shell" in SIDE_EFFECT_TOOLS


def test_write_file_prompts_user(monkeypatch):
    # simulate user typing 'y'
    monkeypatch.setattr("builtins.input", lambda _: "y")
    assert check("write_file", {"path": "out.md", "content": "x"}) is True


def test_write_file_denied_on_n(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert check("write_file", {"path": "out.md", "content": "x"}) is False


def test_write_file_denied_on_empty(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "")
    assert check("write_file", {"path": "out.md", "content": "x"}) is False
