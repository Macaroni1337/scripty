from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import questionary
from questionary import Choice
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from core.theme import COLORS


console = Console()


def _data_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "cheatsheet.json"


def _load() -> Dict[str, Any]:
    p = _data_path()
    if not p.exists():
        return {"categories": []}
    return json.loads(p.read_text(encoding="utf-8"))


def _render_category(name: str, entries: List[Dict[str, str]]) -> None:
    console.print(
        Panel(
            Text("Quick reference without leaving the terminal.", style=COLORS.muted),
            title=Text(name, style=COLORS.primary),
            border_style=COLORS.primary,
            box=box.ROUNDED,
        )
    )

    t = Table(box=box.SIMPLE_HEAVY)
    t.add_column("Command", style=COLORS.primary)
    t.add_column("What it does", style=COLORS.muted)
    t.add_column("When to use it", style=COLORS.muted)
    for e in entries:
        t.add_row(str(e.get("command", "")), str(e.get("what", "")), str(e.get("when", "")))
    console.print(t)


def menu() -> None:
    data = _load()
    cats = data.get("categories", [])
    if not cats:
        console.print(Panel.fit(Text("No cheatsheet data found.", style=COLORS.warning), border_style=COLORS.warning))
        return

    while True:
        try:
            sel = questionary.select(
                "Pick a category",
                choices=[Choice(c["name"], value=c) for c in cats] + [Choice("← Back", value=None, shortcut_key="q")],
                instruction="Use ↑/↓ then Enter. Ctrl+C to go back.",
                use_shortcuts=True,
            ).ask()
        except KeyboardInterrupt:
            return
        if sel is None:
            return
        _render_category(sel["name"], sel.get("entries", []))
        try:
            questionary.text("Press Enter to go back…", default="").ask()
        except KeyboardInterrupt:
            return


if __name__ == "__main__":
    menu()

