from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from core.dependency_check import ToolInfo, check_tool, load_tools
from core.theme import COLORS


console = Console()


@dataclass(frozen=True)
class ToolRequirement:
    ok: bool
    path: Optional[str]
    hint: str


def _tool_index() -> Dict[str, ToolInfo]:
    return {t.binary: t for t in load_tools()}


def require(binary: str, *, friendly_name: Optional[str] = None) -> ToolRequirement:
    path = check_tool(binary)
    if path:
        return ToolRequirement(ok=True, path=path, hint="")

    idx = _tool_index()
    info = idx.get(binary)
    name = friendly_name or (info.name if info else binary)
    hint = ""
    if info and info.apt:
        hint = f"Try: {info.apt}"
    elif info and info.brew:
        hint = f"Try: {info.brew}"

    console.print(
        Panel(
            Text(
                f"{name} ({binary}) is not installed or not on PATH.\n{hint}".strip(),
                style=COLORS.warning,
            ),
            title=Text("Missing dependency", style=COLORS.warning),
            border_style=COLORS.warning,
        )
    )
    return ToolRequirement(ok=False, path=None, hint=hint)

