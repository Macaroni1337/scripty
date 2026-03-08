from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, Optional

import toml

from core.paths import get_paths


@dataclass(frozen=True)
class Config:
    version: str = "1.0.0"
    disclaimer_accepted: bool = False
    default_target: Optional[str] = None
    default_wordlist: Optional[str] = None
    default_output_dir: Optional[str] = None

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Config":
        return Config(
            version=str(d.get("version", "1.0.0")),
            disclaimer_accepted=bool(d.get("disclaimer_accepted", False)),
            default_target=d.get("default_target") or None,
            default_wordlist=d.get("default_wordlist") or None,
            default_output_dir=d.get("default_output_dir") or None,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "disclaimer_accepted": self.disclaimer_accepted,
            "default_target": self.default_target,
            "default_wordlist": self.default_wordlist,
            "default_output_dir": self.default_output_dir,
        }

    def with_updates(self, **kwargs: Any) -> "Config":
        return replace(self, **kwargs)


def ensure_dirs() -> None:
    p = get_paths()
    p.base_dir.mkdir(parents=True, exist_ok=True)
    p.results_dir.mkdir(parents=True, exist_ok=True)
    p.cache_dir.mkdir(parents=True, exist_ok=True)


def load_config() -> Config:
    ensure_dirs()
    p = get_paths()
    if not p.config_path.exists():
        cfg = Config()
        save_config(cfg)
        return cfg
    try:
        data = toml.load(str(p.config_path))
    except Exception:
        # If config is corrupted, don't brick startup.
        return Config()
    if not isinstance(data, dict):
        return Config()
    return Config.from_dict(data)


def save_config(cfg: Config) -> None:
    ensure_dirs()
    p = get_paths()
    tmp = Path(str(p.config_path) + ".tmp")
    tmp.write_text(toml.dumps(cfg.to_dict()), encoding="utf-8")
    tmp.replace(p.config_path)

