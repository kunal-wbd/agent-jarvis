"""Tests for agent._project_listing — the auto-surfaced project tree."""

import pytest

import agent


@pytest.fixture
def calls(monkeypatch):
    """Record run_tool("list_dir", ...) calls; return canned per-path output."""
    seen = []

    def fake_run_tool(name, args):
        seen.append(args["path"])
        return f"LISTING[{args['path']}]"

    monkeypatch.setattr(agent, "run_tool", fake_run_tool)
    return seen


def test_lists_root_and_subdirs(tmp_path, calls):
    (tmp_path / "specs").mkdir()
    (tmp_path / "decisions").mkdir()
    (tmp_path / "notes.md").write_text("x")  # a file, not a dir — should not be listed

    result = agent._project_listing(str(tmp_path))

    assert str(tmp_path) in calls
    assert str(tmp_path / "decisions") in calls
    assert str(tmp_path / "specs") in calls
    assert str(tmp_path / "notes.md") not in calls


def test_skips_hidden_dirs(tmp_path, calls):
    (tmp_path / ".git").mkdir()
    (tmp_path / "specs").mkdir()

    agent._project_listing(str(tmp_path))

    assert str(tmp_path / ".git") not in calls
    assert str(tmp_path / "specs") in calls


def test_only_root_when_no_subdirs(tmp_path, calls):
    result = agent._project_listing(str(tmp_path))
    assert calls == [str(tmp_path)]


def test_nonexistent_path_lists_root_only(tmp_path, calls):
    missing = str(tmp_path / "does-not-exist")
    result = agent._project_listing(missing)
    # os.listdir on a missing dir raises OSError — caught, root call still happened
    assert calls == [missing]
    assert f"LISTING[{missing}]" in result


def test_blocks_joined_with_blank_line(tmp_path, calls):
    (tmp_path / "specs").mkdir()
    result = agent._project_listing(str(tmp_path))
    assert "\n\n" in result
