"""Tests for session/system.py — prompt assembly logic."""

import os
import tempfile

import pytest

from session.system import load_system_prompt, SKILLS_DIR


def test_base_prompt_loads(tmp_path, monkeypatch):
    agents = tmp_path / "agents.md"
    agents.write_text("# PM Persona")
    monkeypatch.setattr("session.system.AGENTS_MD_PATH", str(agents))
    prompt = load_system_prompt()
    assert "# PM Persona" in prompt


def test_missing_agents_md_returns_empty_base(tmp_path, monkeypatch):
    monkeypatch.setattr("session.system.AGENTS_MD_PATH", str(tmp_path / "nonexistent.md"))
    prompt = load_system_prompt()
    assert prompt == ""


def test_project_path_injected(tmp_path, monkeypatch):
    agents = tmp_path / "agents.md"
    agents.write_text("# PM")
    monkeypatch.setattr("session.system.AGENTS_MD_PATH", str(agents))
    prompt = load_system_prompt(project_path="/projects/my-feature")
    assert "Active project" in prompt
    assert "/projects/my-feature" in prompt


def test_active_skill_appended(tmp_path, monkeypatch):
    agents = tmp_path / "agents.md"
    agents.write_text("# PM")
    monkeypatch.setattr("session.system.AGENTS_MD_PATH", str(agents))

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "write-tech-spec.md").write_text("# Tech Spec skill content")
    monkeypatch.setattr("session.system.SKILLS_DIR", str(skills_dir))

    prompt = load_system_prompt(active_skills=["write-tech-spec"])
    assert "Active skills" in prompt
    assert "Tech Spec skill content" in prompt


def test_multiple_skills_appended(tmp_path, monkeypatch):
    agents = tmp_path / "agents.md"
    agents.write_text("# PM")
    monkeypatch.setattr("session.system.AGENTS_MD_PATH", str(agents))

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "skill-a.md").write_text("Skill A content")
    (skills_dir / "skill-b.md").write_text("Skill B content")
    monkeypatch.setattr("session.system.SKILLS_DIR", str(skills_dir))

    prompt = load_system_prompt(active_skills=["skill-a", "skill-b"])
    assert "Skill A content" in prompt
    assert "Skill B content" in prompt


def test_missing_skill_file_skipped_silently(tmp_path, monkeypatch):
    agents = tmp_path / "agents.md"
    agents.write_text("# PM")
    monkeypatch.setattr("session.system.AGENTS_MD_PATH", str(agents))
    monkeypatch.setattr("session.system.SKILLS_DIR", str(tmp_path / "skills"))

    # should not raise, just return base prompt
    prompt = load_system_prompt(active_skills=["nonexistent-skill"])
    assert "# PM" in prompt


def test_project_and_skill_both_present(tmp_path, monkeypatch):
    agents = tmp_path / "agents.md"
    agents.write_text("# PM")
    monkeypatch.setattr("session.system.AGENTS_MD_PATH", str(agents))

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "my-skill.md").write_text("My skill instructions")
    monkeypatch.setattr("session.system.SKILLS_DIR", str(skills_dir))

    prompt = load_system_prompt(active_skills=["my-skill"], project_path="/p/test")
    assert "Active project" in prompt
    assert "/p/test" in prompt
    assert "My skill instructions" in prompt
