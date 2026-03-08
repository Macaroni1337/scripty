from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class SessionState:
    sticky_target: Optional[str] = None

