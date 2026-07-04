"""Tests for tool/stdio/server.py — JSON-RPC handlers without spawning a subprocess."""

import json
import os
import tempfile

import pytest

# Import handler functions directly rather than going through the subprocess
from tool.stdio import server


def _call(method: str, params: dict | None = None) -> dict:
    req = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params:
        req["params"] = params
    dispatch = {
        "initialize": server._handle_initialize,
        "tools/list": server._handle_tools_list,
        "tools/call": server._handle_tools_call,
    }
    return dispatch[method](req)


# ---------------------------------------------------------------------------
# initialize
# ---------------------------------------------------------------------------

def test_initialize_returns_server_info():
    resp = _call("initialize")
    assert "result" in resp
    assert resp["result"]["serverInfo"]["name"] == "harness-stdio"


# ---------------------------------------------------------------------------
# tools/list
# ---------------------------------------------------------------------------

def test_tools_list_returns_all_tools():
    resp = _call("tools/list")
    names = [t["name"] for t in resp["result"]["tools"]]
    assert "read_file" in names
    assert "write_file" in names
    assert "list_dir" in names


def test_tools_list_have_input_schema():
    resp = _call("tools/list")
    for tool in resp["result"]["tools"]:
        assert "inputSchema" in tool
        assert tool["inputSchema"]["type"] == "object"


# ---------------------------------------------------------------------------
# tools/call — read_file
# ---------------------------------------------------------------------------

def test_read_file_returns_content(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("hello harness")
    resp = _call("tools/call", {"name": "read_file", "arguments": {"path": str(f)}})
    text = resp["result"]["content"][0]["text"]
    assert "hello harness" in text


def test_read_file_missing_returns_error(tmp_path):
    resp = _call("tools/call", {"name": "read_file", "arguments": {"path": str(tmp_path / "nope.txt")}})
    text = resp["result"]["content"][0]["text"]
    assert "error" in text


# ---------------------------------------------------------------------------
# tools/call — write_file
# ---------------------------------------------------------------------------

def test_write_file_creates_file(tmp_path):
    path = str(tmp_path / "out.md")
    resp = _call("tools/call", {"name": "write_file", "arguments": {"path": path, "content": "# Spec"}})
    assert "error" not in resp
    assert os.path.exists(path)
    assert open(path).read() == "# Spec"


def test_write_file_creates_parent_dirs(tmp_path):
    path = str(tmp_path / "a" / "b" / "c.txt")
    _call("tools/call", {"name": "write_file", "arguments": {"path": path, "content": "deep"}})
    assert os.path.exists(path)


# ---------------------------------------------------------------------------
# tools/call — list_dir
# ---------------------------------------------------------------------------

def test_list_dir_shows_files(tmp_path):
    (tmp_path / "alpha.md").write_text("")
    (tmp_path / "beta.md").write_text("")
    resp = _call("tools/call", {"name": "list_dir", "arguments": {"path": str(tmp_path)}})
    text = resp["result"]["content"][0]["text"]
    assert "alpha.md" in text
    assert "beta.md" in text


def test_list_dir_empty(tmp_path):
    resp = _call("tools/call", {"name": "list_dir", "arguments": {"path": str(tmp_path)}})
    text = resp["result"]["content"][0]["text"]
    assert "empty" in text


# ---------------------------------------------------------------------------
# tools/call — unknown tool
# ---------------------------------------------------------------------------

def test_unknown_tool_returns_error():
    resp = _call("tools/call", {"name": "does_not_exist", "arguments": {}})
    assert "error" in resp
    assert resp["error"]["code"] == -32601
