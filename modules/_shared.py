from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

import questionary
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from core.runner import RunResult, offer_save_results, run_streaming
from core.theme import COLORS
from core.ui import confirm_run, pause


console = Console()


def header(title: str, subtitle: str) -> None:
    console.print(
        Panel(
            Text.from_markup(subtitle),
            title=Text(title, style=COLORS.primary),
            border_style=COLORS.primary,
            box=box.ROUNDED,
        )
    )


def scripty_says(text: str) -> None:
    console.print(
        Panel(
            Text(text, style=COLORS.primary),
            title=Text("🧠 Scripty says:", style=COLORS.accent),
            border_style=COLORS.accent,
            box=box.ROUNDED,
        )
    )


def next_steps(steps: List[str]) -> None:
    if not steps:
        return
    body = "\n".join(f"• {s}" for s in steps)
    console.print(
        Panel(
            Text(body, style=COLORS.muted),
            title=Text("💡 What to do next:", style=COLORS.primary),
            border_style=COLORS.primary,
            box=box.ROUNDED,
        )
    )


def run_with_preview(
    argv: List[str],
    *,
    title: str,
    module_slug: str,
    warning: Optional[str] = None,
) -> Optional[RunResult]:
    if not confirm_run(argv, warning=warning):
        return None
    res = run_streaming(argv, title=title)
    if res.exit_code == 127:
        console.print(
            Panel.fit(
                Text("Command not found. Is the tool installed?", style=COLORS.warning),
                border_style=COLORS.warning,
                box=box.ROUNDED,
            )
        )
        pause()
        return None
    offer_save_results(module_slug, res.output)
    return res


def simple_kv_table(title: str, rows: List[Tuple[str, str]]) -> None:
    t = Table(title=title, box=box.SIMPLE_HEAVY)
    t.add_column("Key", style=COLORS.primary, no_wrap=True)
    t.add_column("Value", style=COLORS.muted)
    for k, v in rows:
        t.add_row(k, v)
    console.print(t)


def parse_nmap_ports(output: str) -> List[dict]:
    """
    Parse common nmap output table rows like:
      80/tcp   open  http    Apache httpd 2.4.41 ((Ubuntu))
    """
    ports: List[dict] = []
    in_ports = False
    for line in output.splitlines():
        if line.strip().startswith("PORT"):
            in_ports = True
            continue
        if in_ports and (line.strip() == "" or line.startswith("Nmap done:")):
            in_ports = False
            continue
        if not in_ports:
            continue

        m = re.match(r"^(?P<port>\d+)/(tcp|udp)\s+(?P<state>\S+)\s+(?P<service>\S+)(\s+(?P<rest>.*))?$", line.strip())
        if not m:
            continue
        port_proto = line.strip().split()[0]
        proto = "tcp" if "/tcp" in port_proto else "udp"
        ports.append(
            {
                "port": m.group("port"),
                "proto": proto,
                "state": m.group("state"),
                "service": m.group("service"),
                "version": (m.group("rest") or "").strip(),
            }
        )
    return ports


def render_ports_table(ports: List[dict]) -> None:
    t = Table(title="Open ports", box=box.SIMPLE_HEAVY)
    t.add_column("Port", style=COLORS.primary, no_wrap=True)
    t.add_column("Proto", style=COLORS.muted, no_wrap=True)
    t.add_column("State", no_wrap=True)
    t.add_column("Service", style=COLORS.primary)
    t.add_column("Version", style=COLORS.muted)
    for p in ports:
        state = p["state"]
        state_style = COLORS.success if state == "open" else COLORS.warning
        t.add_row(p["port"], p["proto"], f"[{state_style}]{state}[/{state_style}]", p["service"], p["version"])
    console.print(t)

