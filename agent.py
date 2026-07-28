import os
import readline  # noqa: F401 — enables arrow keys, history, and line editing in input()
from util.tracing import init_tracing
init_tracing()  # must run before any tracer is created

from session.session import Session  # noqa: E402
from session.system import SKILLS_DIR, load_system_prompt  # noqa: E402
from config.settings import PROJECTS_DIR
from memory.store import (  # noqa: E402
    init_db, find_session, get_session, list_sessions, load_project_history, load_session,
)
from tool.registry import run_tool  # noqa: E402
from datetime import date as _date_type

SLASH_HELP = """\
  /project <name>      set active project (creates directory if needed)
  /project             show active project
  /skills              list available skills
  /use <skill-name>    activate a skill for this session
  /active              show currently active skills
  /clear-skills        reset to base persona (no active skills)
  /sessions            list past sessions
  /resume <id>         resume a past session (load its message history)
  /session             show current session ID
  /wiki source         show the session history the wiki is built from
  /wiki source --full  show it exactly as the model would receive it
  quit / exit          end the session\
"""

WIKI_HELP = """\
  /wiki source         summary of this project's recorded conversations
  /wiki source --full  the full transcript text, as the model receives it\
"""

def _rebuild_prompt(session, active_skills, project_path):
    session.set_system_prompt(
        load_system_prompt(list(active_skills), project_path)
    )

def print_event(event) -> None:
    if event.type == "text":
        print(f"\n{event.data['text']}")
    elif event.type == "tool_call":
        print(f"  [tool] {event.data['name']}({_fmt(event.data['input'])})")
    elif event.type == "tool_result":
        snippet = str(event.data["result"])[:120]
        print(f"  [done] {event.data['name']} -> {snippet}")
    elif event.type == "max_turns":
        print("\n[max_turns] reached without a final answer")


def _fmt(d: dict) -> str:
    parts = []
    for k, v in d.items():
        s = str(v)
        parts.append(f"{k}={s[:60]!r}" if len(s) > 60 else f"{k}={s!r}")
    return ", ".join(parts)


def _available_skills() -> list[str]:
    try:
        return sorted(
            f[:-3] for f in os.listdir(SKILLS_DIR) if f.endswith(".md")
        )
    except FileNotFoundError:
        return []


def _handle_wiki(args: str, session_ref) -> bool:
    """Handle /wiki subcommands. `args` is everything after the verb."""
    parts = args.split(None, 1)
    action = parts[0].lower() if parts else ""
    flags = parts[1].strip() if len(parts) > 1 else ""

    if action != "source":
        if action:
            print(f"  Unknown wiki command '{action}'.")
        print(WIKI_HELP)
        return True

    # The wiki is built from a project's conversations — without a project
    # there is nothing to read.
    project = session_ref[0].project
    if not project:
        print("  No active project. Run /project <name> first —")
        print("  the wiki is built from a project's session history.")
        return True

    if flags in ("--full", "-f"):
        # Route through the real tool so this shows exactly what the model sees.
        print(run_tool("read_sessions", {"project": project}))
        return True
    if flags:
        print(f"  Unknown option '{flags}'.\n{WIKI_HELP}")
        return True

    history = load_project_history(project)
    if not history:
        print(f"  No recorded conversations for '{project}' yet.")
        print("  Have a conversation first, then run /wiki source again.")
        return True

    total_chars = sum(
        len(m.get("content") or "")
        for s in history
        for m in s["messages"]
        if m["role"] in ("user", "assistant")
    )

    print(f"  Session history for '{project}' — {len(history)} session(s), ~{total_chars:,} chars")
    print()
    print(f"  {'Date':<12} {'Turns':<6} {'Session ID':<38} Opening message")
    print("  " + "-" * 100)
    for s in history:
        first = next((m["content"] for m in s["messages"] if m["role"] == "user"), "")
        preview = " ".join(first.split())[:40]
        print(f"  {s['date']:<12} {s['turn_count']:<6} {s['id']:<38} {preview}")
    print()
    print("  Run /wiki source --full to see the full text the model would read.")
    return True


def _handle_slash(cmd, session_ref, active_skills, project_path_ref):
    """Handle a slash command. Returns True if handled."""
    parts = cmd.split(None, 1)
    verb = parts[0].lower()

    if verb == "/project":
        if len(parts) < 2:
            s = session_ref[0]
            if s.project:
                print(f"  Active project: {s.project}  (session {s.session_id})")
            else:
                print("  No project set. Use: /project <name>")
            return True

        name = parts[1].strip()
        path = os.path.join(PROJECTS_DIR, name)
        os.makedirs(os.path.join(path, "specs"), exist_ok=True)
        os.makedirs(os.path.join(path, "acceptance-criteria"), exist_ok=True)
        os.makedirs(os.path.join(path, "decisions"), exist_ok=True)
        project_path_ref[0] = path

        today = _date_type.today().isoformat()
        existing = find_session(today, name)
        if existing:
            messages = load_session(existing["id"])
            session_ref[0] = Session(
                messages=messages,
                session_id=existing["id"],
                project=name,
            )
            print(f"  Project: {name}  — resuming today's session ({existing['id']}, {existing['turn_count']} turns)")
        else:
            session_ref[0] = Session(project=name)
            print(f"  Project: {name}  — new session ({session_ref[0].session_id})")

        _rebuild_prompt(session_ref[0], active_skills, path)
        return True

    if verb == "/skills":
        skills = _available_skills()
        if skills:
            print("Available skills:")
            for s in skills:
                marker = " (active)" if s in active_skills else ""
                print(f"  {s}{marker}")
        else:
            print("No skills found in skills/")
        return True

    if verb == "/use":
        if len(parts) < 2:
            print("Usage: /use <skill-name>")
            return True
        name = parts[1].strip()
        if name in active_skills:
            print(f"  {name} is already active.")
            return True
        if not os.path.exists(os.path.join(SKILLS_DIR, f"{name}.md")):
            print(f"  Skill '{name}' not found. Run /skills to see what's available.")
            return True
        active_skills.add(name)
        _rebuild_prompt(session_ref[0], active_skills, project_path_ref[0])
        print(f"  Skill '{name}' activated. Active: {sorted(active_skills)}")
        return True

    if verb == "/active":
        if active_skills:
            print(f"Active skills: {sorted(active_skills)}")
        else:
            print("No skills active.")
        return True

    if verb == "/clear-skills":
        active_skills.clear()
        _rebuild_prompt(session_ref[0], active_skills, project_path_ref[0])
        print("  Skills cleared. Back to base persona.")
        return True

    if verb == "/sessions":
        sessions = list_sessions()
        if not sessions:
            print("  No sessions recorded yet.")
        else:
            print(f"  {'Date':<12} {'Project':<20} {'Turns':<6} {'ID'}")
            print("  " + "-" * 76)
            for s in sessions:
                project = (s["project"] or "(none)")[:19]
                print(f"  {s['date']:<12} {project:<20} {s['turn_count']:<6} {s['id']}")
        return True

    if verb == "/resume":
        if len(parts) < 2:
            print("Usage: /resume <session-id>")
            return True
        session_id = parts[1].strip()
        meta = get_session(session_id)
        if meta is None:
            print(f"  Session '{session_id}' not found. Run /sessions to see available sessions.")
            return True

        messages = load_session(session_id)
        if not messages:
            print(f"  Session '{session_id}' has no recorded messages — nothing to resume.")
            return True

        # Continue the same session rather than forking a new one, and carry its
        # project across so later saves stay attached to it.
        project = meta["project"]
        session_ref[0] = Session(
            messages=messages,
            session_id=session_id,
            project=project,
        )

        if project:
            project_path_ref[0] = os.path.join(PROJECTS_DIR, project)
        _rebuild_prompt(session_ref[0], active_skills, project_path_ref[0])

        where = f" in project '{project}'" if project else ""
        print(f"  Resumed session {session_id}{where} ({len(messages)} messages loaded).")
        return True

    if verb == "/session":
        print(f"  Current session ID: {session_ref[0].session_id}")
        return True

    if verb == "/wiki":
        return _handle_wiki(parts[1] if len(parts) > 1 else "", session_ref)

    if verb == "/help":
        print(SLASH_HELP)
        return True

    print(f"  Unknown command '{verb}'.\n{SLASH_HELP}")
    return True


if __name__ == "__main__":
    init_db()

    session_ref: list[Session] = [Session()]
    active_skills: set[str] = set()
    project_path_ref: list[str | None] = [None]

    print(f"Session ID: {session_ref[0].session_id}")
    print("PM spec assistant ready.  /help for commands.\n")

    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("Bye.")
            break

        if user_input.startswith("/"):
            _handle_slash(user_input, session_ref, active_skills, project_path_ref)
            print()
            continue

        for event in session_ref[0].send(user_input):
            print_event(event)
        print()
