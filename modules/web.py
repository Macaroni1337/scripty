from __future__ import annotations

import re
from typing import Dict, List, Optional

import questionary
from questionary import Choice
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from core.config import Config
from core.state import SessionState
from core.theme import COLORS
from core.tools import require
from core.ui import ask_text, pause
from core.wordlists import load_wordlists, resolve_wordlist_path
from modules._shared import header, next_steps, run_with_preview, scripty_says


console = Console()


def _ask_url(state: SessionState) -> Optional[str]:
    default = ""
    if state.sticky_target:
        default = f"http://{state.sticky_target}"
    url = ask_text("Target URL", default=default, placeholder="https://example.com")
    if not url:
        return None
    return url.strip()


def _pick_wordlist(cfg: Config, purpose: str) -> Optional[str]:
    default = resolve_wordlist_path(cfg.default_wordlist)
    known = load_wordlists()
    choices = []
    for wl in known:
        choices.append(Choice(f"{wl.name}  ({wl.path})", value=wl.path))
    choices.append(Choice("Custom path…", value="custom"))
    choices.append(Choice("← Back", value=None))

    sel = questionary.select(f"Wordlist for {purpose}", choices=choices, instruction="Ctrl+C to go back.").ask()
    if sel is None:
        return None
    if sel == "custom":
        p = ask_text("Wordlist path", default=default or "", placeholder="/usr/share/seclists/Discovery/Web-Content/common.txt")
        return p.strip() if p else None
    return sel


def dir_busting(*, state: SessionState, cfg: Config) -> None:
    header("Web Application Testing", "Directory busting is how you find the stuff devs hoped you wouldn’t notice.")
    url = _ask_url(state)
    if not url:
        return
    wl = _pick_wordlist(cfg, "dir busting")
    if not wl:
        return
    exts = ask_text("Extensions (optional)", default="php,txt,html,js", placeholder="Comma-separated, leave blank for none", validate_non_empty=False)
    status = ask_text("Status codes to show", default="200,204,301,302,307,401,403", placeholder="Comma-separated list", validate_non_empty=False)
    tool = questionary.select(
        "Tool",
        choices=[
            Choice("gobuster dir", value="gobuster"),
            Choice("ffuf", value="ffuf"),
            Choice("← Back", value=None, shortcut_key="q"),
        ],
        use_shortcuts=True,
    ).ask()
    if tool is None:
        return

    juicy = ("admin", "login", "backup", "config", ".env", ".git", "wp-admin", "phpmyadmin")
    if tool == "gobuster":
        if not require("gobuster", friendly_name="Gobuster").ok:
            pause()
            return
        argv = ["gobuster", "dir", "-u", url, "-w", wl]
        if exts and exts.strip():
            argv += ["-x", exts.replace(" ", "")]
        if status and status.strip():
            argv += ["-s", status.replace(" ", "")]
        res = run_with_preview(argv, title="gobuster dir", module_slug="web_dirbust_gobuster")
        if not res:
            return
        hits = []
        for ln in res.output.splitlines():
            if ln.strip().startswith("/") and "(" in ln:
                hits.append(ln.strip())
        if hits:
            highlight = [h for h in hits if any(j in h.lower() for j in juicy)]
            scripty_says(f"Found {len(hits)} hit(s). {'Some look spicy.' if highlight else 'Now sanity-check the interesting ones.'}")
            console.print(
                Panel(
                    Text("\n".join((highlight or hits)[:80]), style=COLORS.muted),
                    title=Text("Findings", style=COLORS.primary),
                    border_style=COLORS.primary,
                    box=box.ROUNDED,
                )
            )
        else:
            scripty_says("No obvious hits parsed. Check the raw output and consider different wordlists/status codes.")
    else:
        if not require("ffuf", friendly_name="ffuf").ok:
            pause()
            return
        argv = ["ffuf", "-u", url.rstrip("/") + "/FUZZ", "-w", wl]
        if status and status.strip():
            argv += ["-mc", status.replace(" ", "")]
        if exts and exts.strip():
            argv += ["-e", "." + ",.".join([e.strip().lstrip(".") for e in exts.split(",") if e.strip()])]
        res = run_with_preview(argv, title="ffuf", module_slug="web_dirbust_ffuf")
        if not res:
            return
        scripty_says("ffuf finished. Sort by status/size/words and chase the weird outliers.")

    next_steps(
        [
            "Run WhatWeb / tech fingerprinting to understand the stack.",
            "If you find a login → consider auth bypass, weak creds, or session issues.",
            "Check headers for missing security controls (HSTS/CSP/etc.).",
        ]
    )
    pause()


def nikto_scan(*, state: SessionState) -> None:
    header("Web Application Testing", "Nikto is a noisy web scanner. Use it when you’re allowed to be loud.")
    if not require("nikto", friendly_name="Nikto").ok:
        pause()
        return
    url = _ask_url(state)
    if not url:
        return
    argv = ["nikto", "-h", url]
    res = run_with_preview(argv, title="nikto", module_slug="web_nikto", warning="Nikto is noisy. Expect logs to notice.")
    if not res:
        return
    findings = [ln for ln in res.output.splitlines() if ln.strip().startswith("+")]
    if findings:
        scripty_says(f"Nikto reported {len(findings)} item(s). Triage them; many are informational but some are real problems.")
        console.print(Panel(Text("\n".join(findings[:60]), style=COLORS.muted), title=Text("Nikto findings", style=COLORS.primary), border_style=COLORS.primary, box=box.ROUNDED))
    else:
        scripty_says("No clear findings parsed. Check the raw output.")
    pause()


def whatweb_scan(*, state: SessionState) -> None:
    header("Web Application Testing", "Tech fingerprinting helps you stop guessing and start targeting.")
    if not require("whatweb", friendly_name="WhatWeb").ok:
        pause()
        return
    url = _ask_url(state)
    if not url:
        return
    argv = ["whatweb", url]
    res = run_with_preview(argv, title="whatweb", module_slug="web_whatweb")
    if not res:
        return
    line = next((ln for ln in res.output.splitlines() if ln.strip()), "")
    if line:
        scripty_says("Detected stack hints (best-effort):")
        console.print(Panel(Text(line, style=COLORS.muted), title=Text("WhatWeb", style=COLORS.primary), border_style=COLORS.primary, box=box.ROUNDED))
    pause()


def sqlmap_guided(*, state: SessionState) -> None:
    header("Web Application Testing", "sqlmap is powerful. Also: it can ruin your day if you aim it blindly. Don’t.")
    if not require("sqlmap", friendly_name="sqlmap").ok:
        pause()
        return

    url = _ask_url(state)
    if not url:
        return
    data = ask_text("POST data (optional)", default="", placeholder="Example: username=admin&password=pass", validate_non_empty=False) or ""
    cookies = ask_text("Cookie header (optional)", default="", placeholder="Example: PHPSESSID=...; csrftoken=...", validate_non_empty=False) or ""
    level = ask_text("Level (1-5)", default="1", placeholder="1 (light) → 5 (heavy)", validate_non_empty=False) or "1"
    risk = ask_text("Risk (1-3)", default="1", placeholder="1 (safe-ish) → 3 (spicy)", validate_non_empty=False) or "1"

    argv = ["sqlmap", "--batch", "-u", url, "--level", level.strip(), "--risk", risk.strip()]
    if data.strip():
        argv += ["--data", data.strip()]
    if cookies.strip():
        argv += ["--cookie", cookies.strip()]

    res = run_with_preview(argv, title="sqlmap", module_slug="web_sqlmap", warning="Only run sqlmap with explicit permission. It can be destructive.")
    if not res:
        return

    interesting = []
    for ln in res.output.splitlines():
        if "is vulnerable" in ln.lower() or "parameter" in ln.lower() and "injectable" in ln.lower():
            interesting.append(ln.strip())
    if interesting:
        scripty_says("sqlmap thinks something might be injectable. Verify manually, then decide how deep to go.")
        console.print(Panel(Text("\n".join(interesting[:40]), style=COLORS.muted), title=Text("Signals", style=COLORS.primary), border_style=COLORS.primary, box=box.ROUNDED))
        next_steps(["Confirm injection manually (error-based/boolean/time).", "If confirmed → enumerate DBs/tables with controlled options."])
    else:
        scripty_says("No obvious injection signal parsed. That doesn’t mean ‘safe’; it means ‘not trivially detected’.")
    pause()


def xss_fuzz(*, state: SessionState, cfg: Config) -> None:
    header("Web Application Testing", "XSS fuzzing is about finding reflection and weird behavior — then proving impact safely.")
    if not require("ffuf", friendly_name="ffuf").ok:
        pause()
        return
    url = ask_text("URL with FUZZ placeholder", default="", placeholder="Example: https://site/search?q=FUZZ")
    if not url or "FUZZ" not in url:
        scripty_says("You need a URL containing FUZZ (the injection point).")
        pause()
        return
    wl = _pick_wordlist(cfg, "XSS fuzzing")
    if not wl:
        return
    argv = ["ffuf", "-u", url, "-w", wl, "-mc", "200,302,301,500"]
    res = run_with_preview(argv, title="ffuf XSS", module_slug="web_xss_fuzz")
    if not res:
        return
    scripty_says("Look for responses with odd sizes/words, then test a small set of payloads manually with proper encoding.")
    pause()


def header_analysis(*, state: SessionState) -> None:
    header("Web Application Testing", "Headers won’t save a broken app, but missing ones can make exploitation easier.")
    if not require("curl", friendly_name="curl").ok:
        pause()
        return
    url = _ask_url(state)
    if not url:
        return
    argv = ["curl", "-I", "-s", url]
    res = run_with_preview(argv, title="curl -I", module_slug="web_headers")
    if not res:
        return

    headers: Dict[str, str] = {}
    for ln in res.output.splitlines():
        if ":" in ln:
            k, v = ln.split(":", 1)
            headers[k.strip().lower()] = v.strip()

    required = {
        "content-security-policy": "CSP",
        "strict-transport-security": "HSTS",
        "x-frame-options": "X-Frame-Options",
        "x-content-type-options": "X-Content-Type-Options",
        "referrer-policy": "Referrer-Policy",
        "permissions-policy": "Permissions-Policy",
    }

    t = Table(title="Security headers", box=box.SIMPLE_HEAVY)
    t.add_column("Header", style=COLORS.primary)
    t.add_column("Status")
    t.add_column("Value", style=COLORS.muted)

    missing = []
    for key, label in required.items():
        if key in headers:
            t.add_row(label, f"[{COLORS.success}]present[/{COLORS.success}]", headers[key][:120])
        else:
            t.add_row(label, f"[{COLORS.error}]missing[/{COLORS.error}]", "")
            missing.append(label)
    console.print(t)

    if missing:
        scripty_says("Missing headers don’t guarantee a vuln, but they remove safety rails. Flag them in your report.")
        next_steps(["If HTTPS is in use → missing HSTS is a common finding.", "If the app is complex → a CSP can reduce XSS impact."])
    else:
        scripty_says("Nice — the basic security headers are present. Still review their quality (weak CSPs exist).")
    pause()


def menu(*, state: SessionState, cfg: Config) -> None:
    while True:
        header("Web Application Testing", "Bust dirs, scan for vulns, fuzz inputs. Stay legal. Stay sharp.")
        try:
            sel = questionary.select(
                "Pick a web action",
                choices=[
                    Choice("2.1 Directory & File Busting", value="dir"),
                    Choice("2.2 Nikto Web Scan", value="nikto"),
                    Choice("2.3 WhatWeb / Tech Fingerprinting", value="whatweb"),
                    Choice("2.4 SQL Injection — sqlmap (guided)", value="sqlmap"),
                    Choice("2.5 XSS / Input Fuzzing (ffuf)", value="xss"),
                    Choice("2.6 HTTP Header Analysis", value="headers"),
                    Choice("← Back", value=None, shortcut_key="q"),
                ],
                instruction="Ctrl+C to go back.",
                use_shortcuts=True,
            ).ask()
        except KeyboardInterrupt:
            return

        if sel is None:
            return
        if sel == "dir":
            dir_busting(state=state, cfg=cfg)
        elif sel == "nikto":
            nikto_scan(state=state)
        elif sel == "whatweb":
            whatweb_scan(state=state)
        elif sel == "sqlmap":
            sqlmap_guided(state=state)
        elif sel == "xss":
            xss_fuzz(state=state, cfg=cfg)
        elif sel == "headers":
            header_analysis(state=state)


if __name__ == "__main__":
    menu(state=SessionState(sticky_target=None), cfg=Config())

