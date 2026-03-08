from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScriptyColors:
    primary: str = "bright_cyan"
    accent: str = "magenta"
    success: str = "bright_green"
    warning: str = "yellow"
    error: str = "bright_red"
    muted: str = "grey50"


COLORS = ScriptyColors()

