from __future__ import annotations

import datetime as dt
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import questionary
from rich import box
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from core.paths import get_paths
from core.theme import COLORS


console = Console()


@dataclass(frozen=True)
class RunResult:
    argv: List[str]
    exit_code: int
    output: str


def _render_output_panel(title: str, lines: List[str], *, running: bool) -> Panel:
    suffix = " (running…)" if running else ""
    text = Text("\n".join(lines[-200:]) if lines else "", style=COLORS.muted)
    return Panel(
        text,
        title=Text(f"{title}{suffix}", style=COLORS.primary),
        border_style=COLORS.primary,
        box=box.ROUNDED,
    )


def run_streaming(argv: List[str], *, title: str = "Running", cwd: Optional[str] = None) -> RunResult:
    # Stream stdout/stderr live, but also capture for parsing/saving.
    lines: List[str] = []
    try:
        proc = subprocess.Popen(
            argv,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )
    except FileNotFoundError:
        return RunResult(argv=argv, exit_code=127, output="")

    with Live(_render_output_panel(title, lines, running=True), refresh_per_second=12, console=console) as live:
        assert proc.stdout is not None
        try:
            for raw in proc.stdout:
                line = raw.rstrip("\n")
                lines.append(line)
                live.update(_render_output_panel(title, lines, running=True))
        except KeyboardInterrupt:
            proc.terminate()
        finally:
            try:
                proc.wait(timeout=3)
            except Exception:
                proc.kill()

        live.update(_render_output_panel(title, lines, running=False))

    return RunResult(argv=argv, exit_code=int(proc.returncode or 0), output="\n".join(lines))


def offer_save_results(module_slug: str, raw_output: str) -> Optional[Path]:
    if not raw_output.strip():
        return None
    try:
        do_save = bool(questionary.confirm("Save raw output to ~/.scripty/results/?", default=True).ask())
    except KeyboardInterrupt:
        return None
    if not do_save:
        return None

    p = get_paths()
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = p.results_dir / f"{ts}_{module_slug}.txt"
    out_path.write_text(raw_output, encoding="utf-8", errors="replace")
    console.print(Panel.fit(Text(str(out_path), style=COLORS.success), title="Saved", border_style=COLORS.success, box=box.ROUNDED))
    return out_path

