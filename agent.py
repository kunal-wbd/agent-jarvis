import os
import readline  # noqa: F401 — enables arrow keys, history, and line editing in input()
from util.tracing import init_tracing
init_tracing()  # must run before any tracer is created

from session.session import Session  # noqa: E402
from session.system import SKILLS_DIR, load_system_prompt  # noqa: E402
from config.settings import PROJECTS_DIR

SLASH_HELP = """\
  /project <name>      set active project (creates directory if needed)
  /project             show active project
  /skills              list available skills
  /use <skill-name>    activate a skill for this session
  /active              show currently active skills
  /clear-skills        reset to base persona (no active skills)
  quit / exit          end the session\
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


def _handle_slash(cmd, session, active_skills, project_path_ref):
    """Handle a slash command. Returns True if handled, False if unknown."""
    parts = cmd.split(None, 1)
    verb = parts[0].lower()

    if verb == "/project":
        if len(parts) < 2:
            if project_path_ref[0]:
                print(f"  Active project: {project_path_ref[0]}")
            else:
                print("  No project set. Use: /project <name>")
            return False

        name = parts[1].strip()
        path = os.path.join(PROJECTS_DIR, name)
        os.makedirs(os.path.join(path, "specs"), exist_ok=True)
        os.makedirs(os.path.join(path, "acceptance-criteria"), exist_ok=True)
        os.makedirs(os.path.join(path, "decisions"), exist_ok=True)
        project_path_ref[0] = path
        _rebuild_prompt(session, active_skills, path)
        print(f"  Project: {name}  ({path})")
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
        _rebuild_prompt(session, active_skills, project_path_ref[0])
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
        _rebuild_prompt(session, active_skills, project_path_ref[0])
        print("  Skills cleared. Back to base persona.")
        return True

    print(f"  Unknown command '{verb}'.\n{SLASH_HELP}")
    return True


if __name__ == "__main__":
    session = Session()
    active_skills: set[str] = set()
    project_path_ref: list[str | None] = [None]  # mutable reference so _handle_slash can update it
    print("PM spec assistant ready.  /skills to browse, /use <name> to activate.\n")

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
            _handle_slash(user_input, session, active_skills, project_path_ref)
            print()
            continue

        for event in session.send(user_input):
            print_event(event)
        print()
