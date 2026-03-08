from __future__ import annotations

import os
import platform
import shlex
import sys
import time
from dataclasses import dataclass
from typing import Iterable, List, Optional

import questionary
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from core.theme import COLORS


console = Console()


def clear_screen() -> None:
    if os.name == "nt":
        os.system("cls")
    else:
        os.system("clear")


def scripty_panel(title: str, body: str, *, style: str | None = None) -> Panel:
    return Panel(
        Text.from_markup(body),
        title=Text(title, style=style or COLORS.primary),
        border_style=style or COLORS.primary,
        box=box.ROUNDED,
    )


def print_banner(version: str) -> None:
    # Lightweight “typewriter” effect so startup feels alive without being slow.
    banner_lines = [
        "  ███████╗ ██████╗██████╗ ██╗██████╗ ████████╗██╗   ██╗",
        "  ██╔════╝██╔════╝██╔══██╗██║██╔══██╗╚══██╔══╝╚██╗ ██╔╝",
        "  ███████╗██║     ██████╔╝██║██████╔╝   ██║    ╚████╔╝ ",
        "  ╚════██║██║     ██╔══██╗██║██╔═══╝    ██║     ╚██╔╝  ",
        "  ███████║╚██████╗██║  ██║██║██║        ██║      ██║   ",
        "  ╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝╚═╝        ╚═╝      ╚═╝   ",
        "",
        "          [ pentesting for the rest of us ]",
        f"                      v{version}",
    ]

    # Cyan with magenta accents “feel”
    for line in banner_lines:
        if "[" in line and "]" in line:
            console.print(Text(line, style=COLORS.accent))
        elif line.strip().startswith("v"):
            console.print(Text(line, style=COLORS.muted))
        else:
            console.print(Text(line, style=COLORS.primary))
        time.sleep(0.015)


def syntax_command(argv: List[str]) -> Syntax:
    rendered = shlex.join(argv) if hasattr(shlex, "join") else " ".join(shlex.quote(a) for a in argv)
    return Syntax(rendered, "bash", theme="monokai", line_numbers=False, word_wrap=True)


def confirm_run(argv: List[str], *, warning: Optional[str] = None) -> bool:
    console.print(Panel.fit(syntax_command(argv), title="Command preview", border_style=COLORS.accent, box=box.ROUNDED))
    if warning:
        console.print(Panel(Text(warning, style=COLORS.warning), title="Heads up", border_style=COLORS.warning, box=box.ROUNDED))
    try:
        return bool(questionary.confirm("Run this?", default=True).ask())
    except KeyboardInterrupt:
        return False


def ask_text(
    prompt: str,
    *,
    default: Optional[str] = None,
    placeholder: Optional[str] = None,
    validate_non_empty: bool = True,
) -> Optional[str]:
    def _validate(v: str) -> bool | str:
        if not validate_non_empty:
            return True
        return True if v and v.strip() else "Required"

    try:
        return questionary.text(
            prompt,
            default=default or "",
            validate=_validate,
            qmark="›",
            instruction=placeholder or "",
        ).ask()
    except KeyboardInterrupt:
        return None


def pause(msg: str = "Press Enter to continue…") -> None:
    try:
        questionary.text(msg, default="").ask()
    except KeyboardInterrupt:
        return


def host_os_label() -> str:
    return f"{platform.system()} {platform.release()}"

