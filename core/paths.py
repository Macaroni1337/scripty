from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ScriptyPaths:
    base_dir: Path
    config_path: Path
    results_dir: Path
    cache_dir: Path


def get_paths() -> ScriptyPaths:
    base = Path.home() / ".scripty"
    return ScriptyPaths(
        base_dir=base,
        config_path=base / "config.toml",
        results_dir=base / "results",
        cache_dir=base / "cache",
    )

