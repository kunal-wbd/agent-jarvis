SIDE_EFFECT_TOOLS = {"write_file", "shell"}


def check(tool_name: str, tool_input: dict) -> bool:
    if tool_name not in SIDE_EFFECT_TOOLS:
        return True
    return _prompt_user(tool_name, tool_input)


def _prompt_user(tool_name: str, tool_input: dict) -> bool:
    print(f"\n[permission] {tool_name} wants to run with:")
    for k, v in tool_input.items():
        preview = str(v)
        if len(preview) > 200:
            preview = preview[:200] + "..."
        print(f"             {k}: {preview}")
    answer = input("Allow? [y/N] ").strip().lower()
    return answer in ("y", "yes")
