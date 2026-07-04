import os
from config.settings import AGENTS_MD_PATH

SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")

def load_system_prompt(active_skills: list[str] | None = None, project_path: str | None = None,) -> str:
    try:
        base = open(AGENTS_MD_PATH).read().strip()
    except FileNotFoundError:
        base = ""

    if project_path:
        base += f"\n\n## Active project\n\nAll file operations are scoped to: `{project_path}`\nUse this path as the root when calling `write_file`, `list_dir`, or `read_file`.\nAlways call `list_dir` on this directory before creating any new file."
        
    if not active_skills:
        return base

    skill_blocks = []
    for name in active_skills:
        path = os.path.join(SKILLS_DIR, f"{name}.md")
        try:
            skill_blocks.append(open(path).read().strip())
        except FileNotFoundError:
            pass  # silently skip missing skills

    if not skill_blocks:
        return base

    return base + "\n\n## Active skills\n\n" + "\n\n---\n\n".join(skill_blocks)
