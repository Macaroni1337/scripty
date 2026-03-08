from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class Wordlist:
    name: str
    path: str


def _data_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "wordlists.json"


def load_wordlists() -> List[Wordlist]:
    p = _data_path()
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    out: List[Wordlist] = []
    for wl in data.get("wordlists", []):
        out.append(Wordlist(name=str(wl["name"]), path=str(wl["path"])))
    return out


def resolve_wordlist_path(preferred: Optional[str]) -> Optional[str]:
    if preferred:
        return preferred
    # pick first existing system list if any
    for wl in load_wordlists():
        if Path(wl.path).exists():
            return wl.path
    return None

