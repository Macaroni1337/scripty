from __future__ import annotations

import questionary
from questionary import Choice
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from core.config import Config
from core.state import SessionState
from core.theme import COLORS
from core.ui import pause

from modules import (
    cheatsheet,
    exploitation,
    network,
    passwords,
    post_exploit,
    recon,
    toolkit,
    web,
)


console = Console()


def _title_panel(cfg: Config) -> None:
    console.print(
        Panel(
            Text("What do you want to do?", style=COLORS.primary),
            title=Text(f"S C R I P T Y  v{cfg.version}", style=COLORS.primary),
            subtitle=Text("pentesting for the rest of us", style=COLORS.muted),
            border_style=COLORS.primary,
            box=box.ROUNDED,
        )
    )


def main_menu(*, state: SessionState, cfg: Config) -> None:
    while True:
        _title_panel(cfg)
        try:
            sel = questionary.select(
                "",
                choices=[
                    Choice("🔍  Reconnaissance", value="recon", description="Map the target, find open doors"),
                    Choice("🌐  Web Application Testing", value="web", description="Bust dirs, scan for vulns, fuzz inputs"),
                    Choice("💥  Exploitation", value="exploit", description="Run known attacks against services"),
                    Choice("🔑  Password Attacks", value="passwords", description="Brute force, wordlists, hash cracking"),
                    Choice("📡  Network & Traffic", value="network", description="Sniff packets, scan services, reverse shells"),
                    Choice("🗺️  Post-Exploitation", value="post", description="Enumerate, escalate, persist"),
                    Choice("🧰  Toolkit & Settings", value="toolkit", description="Configure Scripty, manage wordlists"),
                    Choice("📖  Cheat Sheet", value="cheatsheet", description="Quick reference without leaving the terminal"),
                    Choice("🚪  Exit", value="exit", description="Leave Scripty", shortcut_key="q"),
                ],
                instruction="Use ↑/↓ then Enter. Press Ctrl+C to go back.",
                use_shortcuts=True,
            ).ask()
        except KeyboardInterrupt:
            return

        if sel == "exit" or sel is None:
            return
        if sel == "recon":
            recon.menu(state=state, cfg=cfg)
        elif sel == "web":
            web.menu(state=state, cfg=cfg)
        elif sel == "exploit":
            exploitation.menu(state=state, cfg=cfg)
        elif sel == "passwords":
            passwords.menu(state=state, cfg=cfg)
        elif sel == "network":
            network.menu(state=state, cfg=cfg)
        elif sel == "post":
            post_exploit.menu(state=state, cfg=cfg)
        elif sel == "toolkit":
            toolkit.menu(state=state, cfg=cfg)
        elif sel == "cheatsheet":
            cheatsheet.menu()
        else:
            pause()

