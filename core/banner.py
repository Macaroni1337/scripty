from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from core.theme import COLORS
from core.ui import print_banner


console = Console()


def show_launch_banner(version: str) -> None:
    print_banner(version)
    console.print(
        Panel.fit(
            Text("Scripty is for authorized testing only.", style=COLORS.warning),
            title=Text("Disclaimer", style=COLORS.warning),
            border_style=COLORS.warning,
        )
    )

