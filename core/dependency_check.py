from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rich.console import Console
from rich.table import Table

from core.theme import COLORS


console = Console()


@dataclass(frozen=True)
class ToolInfo:
    name: str
    binary: str
    apt: Optional[str] = None
    brew: Optional[str] = None


def _data_path() -> Path:
    # data/ is at repo root next to scripty.py
    return Path(__file__).resolve().parents[1] / "data" / "common_tools.json"


def load_tools() -> List[ToolInfo]:
    p = _data_path()
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    tools: List[ToolInfo] = []
    for item in data.get("tools", []):
        tools.append(
            ToolInfo(
                name=str(item["name"]),
                binary=str(item["binary"]),
                apt=item.get("apt"),
                brew=item.get("brew"),
            )
        )
    return tools


def check_tool(binary: str) -> Optional[str]:
    return shutil.which(binary)


def check_all() -> List[Tuple[ToolInfo, bool, Optional[str]]]:
    results: List[Tuple[ToolInfo, bool, Optional[str]]] = []
    for t in load_tools():
        path = check_tool(t.binary)
        results.append((t, bool(path), path))
    return results


def render_dependency_table(rows: List[Tuple[ToolInfo, bool, Optional[str]]]) -> Table:
    table = Table(title="Tool check", show_lines=False)
    table.add_column("Tool", style=COLORS.primary)
    table.add_column("Binary", style=COLORS.muted)
    table.add_column("Status", justify="center")
    table.add_column("Hint", style=COLORS.muted)

    is_kali_like = os.name != "nt"
    for info, ok, _path in rows:
        if ok:
            status = f"[{COLORS.success}]✓ found[/{COLORS.success}]"
            hint = ""
        else:
            status = f"[{COLORS.error}]✗ missing[/{COLORS.error}]"
            if is_kali_like and info.apt:
                hint = f"apt: {info.apt}"
            elif info.brew:
                hint = f"brew: {info.brew}"
            else:
                hint = ""
        table.add_row(info.name, info.binary, status, hint)
    return table

