"""Validate model-supplied arguments before previewing or executing tools."""

from .bash_tool import BASH_TOOL
from .edit_tool import EDIT_TOOL
from .read_tool import READ_TOOL
from .write_tool import WRITE_TOOL

TOOLS = [READ_TOOL, WRITE_TOOL, EDIT_TOOL, BASH_TOOL]


def tool_input_error(name: str, arguments: object) -> str | None:
    """Check the flat schemas of the offered tools without coercing values.

    Additional properties remain allowed, as in the published schemas. Tool
    implementations still handle domain errors such as an out-of-range offset
    or an edit whose old text does not match the file.
    """
    tool = next((tool for tool in TOOLS if tool["name"] == name), None)
    if tool is None:
        return f"Unknown tool: {name}. Use one of: read, write, edit, bash."
    if not isinstance(arguments, dict):
        return "Invalid tool arguments: expected a JSON object. Provide it and retry."
    schema = tool["input_schema"]
    missing = [key for key in schema["required"] if key not in arguments]
    if missing:
        return (
            f"Missing required argument(s): {', '.join(missing)}. "
            "Provide the missing arguments and retry."
        )
    types = {"string": str, "integer": int, "boolean": bool}
    for key, definition in schema["properties"].items():
        if key not in arguments:
            continue
        expected = definition["type"]
        # bool is an int subclass in Python, but not a JSON integer.
        if type(arguments[key]) is not types[expected]:
            return f"Invalid argument: {key} must be {expected}. Correct it and retry."
        if key in {"path", "command"} and "\x00" in arguments[key]:
            return f"Invalid argument: {key} contains a NUL character. Remove it and retry."
    return None
