from __future__ import annotations

import sys

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from core.banner import show_launch_banner
from core.config import load_config, save_config
from core.dependency_check import check_all, render_dependency_table
from core.menu import main_menu
from core.state import SessionState
from core.theme import COLORS
from core.ui import clear_screen, pause


console = Console()


def _ensure_disclaimer(cfg) -> bool:
    if cfg.disclaimer_accepted:
        return True
    console.print(
        Panel(
            Text(
                "Scripty is for use on systems you own or have explicit written permission to test.\n"
                "Unauthorized access is illegal.\n\n"
                "Type AGREE to continue.",
                style=COLORS.warning,
            ),
            title=Text("Before we start", style=COLORS.warning),
            border_style=COLORS.warning,
        )
    )
    try:
        resp = questionary.text("Type AGREE", default="").ask()
    except KeyboardInterrupt:
        return False
    if (resp or "").strip().upper() != "AGREE":
        console.print(Panel.fit(Text("No agreement, no mischief. Bye.", style=COLORS.error), border_style=COLORS.error))
        pause()
        return False
    save_config(cfg.with_updates(disclaimer_accepted=True))
    return True


def run_interactive(*, initial_target: str | None = None) -> None:
    if not sys.stdin.isatty():
        console.print(
            Panel.fit(
                Text(
                    "Interactive mode needs a real TTY.\n"
                    "Run this in a normal terminal (not a redirected/non-interactive shell).",
                    style=COLORS.warning,
                ),
                border_style=COLORS.warning,
            )
        )
        return

    cfg = load_config()
    state = SessionState(sticky_target=initial_target or cfg.default_target)

    clear_screen()
    show_launch_banner(cfg.version)

    if not _ensure_disclaimer(cfg):
        return

    rows = check_all()
    if rows:
        console.print(render_dependency_table(rows))

    main_menu(state=state, cfg=cfg)

