from __future__ import annotations

import re
from typing import List, Optional

import questionary
from questionary import Choice
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from core.config import Config
from core.state import SessionState
from core.theme import COLORS
from core.tools import require
from core.ui import ask_text, pause
from modules._shared import (
    header,
    next_steps,
    parse_nmap_ports,
    render_ports_table,
    run_with_preview,
    scripty_says,
)


console = Console()


def _ask_target(state: SessionState) -> Optional[str]:
    target = ask_text(
        "Target IP/hostname",
        default=state.sticky_target or "",
        placeholder="Example: 10.10.10.10 or example.com",
    )
    if target is None:
        return None
    state.sticky_target = target.strip()
    return state.sticky_target


def nmap_basic_port_scan(*, state: SessionState) -> None:
    header("Reconnaissance", "Nmap is how you knock on every door and see who answers.")
    if not require("nmap", friendly_name="Nmap").ok:
        pause()
        return
    target = _ask_target(state)
    if not target:
        return

    scan = questionary.select(
        "Scan type",
        choices=[
            Choice("Quick (top ports)  (-T4 -F)", value=["-T4", "-F"]),
            Choice("Full (all ports)   (-T4 -p-)", value=["-T4", "-p-"]),
            Choice("Stealth SYN        (-sS)", value=["-sS"]),
            Choice("Version + scripts  (-sV -sC)", value=["-sV", "-sC"]),
            Choice("Vuln scripts       (--script vuln)", value=["--script", "vuln"]),
            Choice("Custom flags…", value="custom"),
            Choice("← Back", value=None, shortcut_key="q"),
        ],
        instruction="Pick one. Ctrl+C to bail.",
        use_shortcuts=True,
    ).ask()
    if scan is None:
        return
    flags: List[str]
    if scan == "custom":
        raw = ask_text("Custom nmap flags", default="-T4 -sV -sC", placeholder="Example: -T4 -sV -sC -p 22,80")
        if not raw:
            return
        flags = raw.split()
    else:
        flags = scan

    argv = ["nmap", *flags, target]
    res = run_with_preview(argv, title="nmap", module_slug="recon_nmap_basic")
    if not res:
        return

    ports = parse_nmap_ports(res.output)
    if ports:
        render_ports_table(ports)
        open_ports = [p for p in ports if p["state"] == "open"]
        scripty_says(f"Found {len(open_ports)} open port(s). That's your attack surface. Treat it like a buffet, not a checklist.")
        steps: List[str] = []
        for p in open_ports:
            if p["port"] in {"80", "443", "8080", "8000"} or p["service"] in {"http", "https"}:
                steps.append("Port 80/443-ish is open → jump to Web Application Testing (dir busting + tech fingerprinting).")
                break
        if any(p["port"] in {"445", "139"} or "microsoft-ds" in p["service"] for p in open_ports):
            steps.append("SMB (445/139) looks alive → try Post-Exploitation → enum4linux and SMB share listing.")
        if any(p["port"] == "22" or p["service"] == "ssh" for p in open_ports):
            steps.append("SSH is open → consider password spray (carefully) or look for keys/users from enumeration.")
        next_steps(steps[:3])
    else:
        scripty_says("No parsable port table found. Either the scan found nothing, or nmap output format was weird. Still saved raw output if you asked.")

    pause()


def nmap_os_detection(*, state: SessionState) -> None:
    header("Reconnaissance", "OS detection gives you a vibe-check on what you're poking.")
    if not require("nmap", friendly_name="Nmap").ok:
        pause()
        return
    target = _ask_target(state)
    if not target:
        return

    argv = ["nmap", "-O", "--osscan-guess", target]
    res = run_with_preview(argv, title="nmap -O", module_slug="recon_nmap_os")
    if not res:
        return

    os_lines: List[str] = []
    for line in res.output.splitlines():
        if line.startswith("OS details:") or line.startswith("Running:") or line.startswith("Aggressive OS guesses:"):
            os_lines.append(line.strip())
    if os_lines:
        scripty_says("\n".join(os_lines[:6]))
    else:
        scripty_says("OS detection didn’t give a clean answer. That can happen if the target blocks probes or there isn’t enough signal.")
    pause()


def ping_sweep(*, state: SessionState) -> None:
    header("Reconnaissance", "Host discovery finds who's alive in a range. Then you can be annoying to the right boxes.")
    if not require("nmap", friendly_name="Nmap").ok:
        pause()
        return
    cidr = ask_text("CIDR range", default="", placeholder="Example: 10.10.10.0/24")
    if not cidr:
        return
    argv = ["nmap", "-sn", cidr]
    res = run_with_preview(argv, title="nmap -sn", module_slug="recon_ping_sweep")
    if not res:
        return

    hosts: List[str] = []
    for line in res.output.splitlines():
        m = re.search(r"Nmap scan report for (.+)$", line)
        if m:
            hosts.append(m.group(1).strip())
    if hosts:
        scripty_says(f"Found {len(hosts)} live host(s). Start port scanning the interesting ones.")
        console.print(Panel(Text("\n".join(hosts[:80]), style=COLORS.muted), title=Text("Live hosts", style=COLORS.primary), border_style=COLORS.primary, box=box.ROUNDED))
        next_steps(["Pick a host → run Nmap Basic Port Scan.", "If it's a subnet lab → save results for later reporting."])
    else:
        scripty_says("No live hosts parsed. Could be ICMP blocked; try a port-based discovery scan.")
    pause()


def whois_lookup() -> None:
    header("Reconnaissance", "WHOIS is for when you want to know who owns the thing (and when it was registered).")
    if not require("whois", friendly_name="whois").ok:
        pause()
        return
    q = ask_text("Domain/IP", default="", placeholder="example.com or 1.2.3.4")
    if not q:
        return
    argv = ["whois", q]
    res = run_with_preview(argv, title="whois", module_slug="recon_whois")
    if not res:
        return

    interesting = []
    keys = ("Registrar", "Creation Date", "Updated Date", "Registry Expiry Date", "Name Server", "OrgName", "Organization")
    for line in res.output.splitlines():
        if any(line.lower().startswith(k.lower()) for k in keys):
            interesting.append(line.strip())
    if interesting:
        scripty_says("Pulled key WHOIS fields (registrar / dates / name servers).")
        console.print(Panel(Text("\n".join(interesting[:25]), style=COLORS.muted), title=Text("Highlights", style=COLORS.primary), border_style=COLORS.primary, box=box.ROUNDED))
    else:
        scripty_says("WHOIS output varies wildly by TLD and registry. Check the raw output for the juicy bits.")
    pause()


def dns_enum() -> None:
    header("Reconnaissance", "DNS enumeration helps you map a domain’s public-facing surface area.")
    domain = ask_text("Domain", default="", placeholder="example.com")
    if not domain:
        return

    # Prefer dig if present, fall back to nslookup/host if not.
    dig_ok = require("dig", friendly_name="dig").ok
    host_ok = require("host", friendly_name="host").ok
    nslookup_ok = require("nslookup", friendly_name="nslookup").ok
    if not (dig_ok or host_ok or nslookup_ok):
        scripty_says("I need at least one of: dig / host / nslookup.")
        pause()
        return

    if dig_ok:
        queries = [("A", "A"), ("MX", "MX"), ("TXT", "TXT"), ("NS", "NS")]
        for label, qtype in queries:
            res = run_with_preview(["dig", "+short", domain, qtype], title=f"dig {qtype}", module_slug=f"recon_dns_{qtype.lower()}")
            if not res:
                return
        scripty_says("DNS lookups ran. If you control an NS and misconfigs exist, try zone transfer (AXFR).")
        axfr = run_with_preview(["dig", "AXFR", domain], title="dig AXFR", module_slug="recon_dns_axfr", warning="AXFR usually fails unless misconfigured. Worth a shot.")
        if axfr:
            if "Transfer failed" in axfr.output or "XFR size" not in axfr.output:
                scripty_says("AXFR didn’t look successful (normal). If you found NS records, try AXFR against each nameserver explicitly.")
            else:
                scripty_says("AXFR might have succeeded. That’s a misconfiguration and usually a goldmine.")
    else:
        if host_ok:
            run_with_preview(["host", domain], title="host", module_slug="recon_dns_host")
        if nslookup_ok:
            run_with_preview(["nslookup", domain], title="nslookup", module_slug="recon_dns_nslookup")
        scripty_says("DNS basic lookups ran. For deeper recon, use dnsrecon or passive sources.")
    pause()


def menu(*, state: SessionState, cfg: Config) -> None:
    while True:
        header("Reconnaissance", "Map the target, find open doors. Don’t brute force what you haven’t identified yet.")
        try:
            sel = questionary.select(
                "Pick a recon action",
                choices=[
                    Choice("1.1 Nmap — Basic Port Scan", value="nmap_basic"),
                    Choice("1.2 Nmap — OS Detection", value="nmap_os"),
                    Choice("1.3 DNS Enumeration", value="dns"),
                    Choice("1.4 WHOIS Lookup", value="whois"),
                    Choice("1.5 Subdomain Enumeration (gobuster/ffuf)", value="subdomains"),
                    Choice("1.6 Ping Sweep / Host Discovery", value="sweep"),
                    Choice("← Back", value=None, shortcut_key="q"),
                ],
                instruction="Ctrl+C to go back.",
                use_shortcuts=True,
            ).ask()
        except KeyboardInterrupt:
            return

        if sel is None:
            return
        if sel == "nmap_basic":
            nmap_basic_port_scan(state=state)
        elif sel == "nmap_os":
            nmap_os_detection(state=state)
        elif sel == "dns":
            dns_enum()
        elif sel == "whois":
            whois_lookup()
        elif sel == "subdomains":
            subdomain_enum(state=state, cfg=cfg)
        elif sel == "sweep":
            ping_sweep(state=state)


def _pick_wordlist(cfg: Config, purpose: str) -> Optional[str]:
    from core.wordlists import load_wordlists, resolve_wordlist_path

    default = resolve_wordlist_path(cfg.default_wordlist)
    known = load_wordlists()
    choices = []
    for wl in known:
        label = f"{wl.name}  ({wl.path})"
        choices.append(Choice(label, value=wl.path))
    choices.append(Choice("Custom path…", value="custom"))
    choices.append(Choice("← Back", value=None))

    sel = questionary.select(f"Wordlist for {purpose}", choices=choices, instruction="Ctrl+C to go back.").ask()
    if sel is None:
        return None
    if sel == "custom":
        p = ask_text("Wordlist path", default=default or "", placeholder="/usr/share/wordlists/rockyou.txt")
        return p.strip() if p else None
    return sel


def subdomain_enum(*, state: SessionState, cfg: Config) -> None:
    header("Reconnaissance", "Subdomains are extra doors. Sometimes they forget to lock them.")
    domain = ask_text("Domain", default="", placeholder="example.com")
    if not domain:
        return
    wl = _pick_wordlist(cfg, "subdomain enumeration")
    if not wl:
        return

    tool = questionary.select(
        "Tool",
        choices=[
            Choice("gobuster dns", value="gobuster"),
            Choice("ffuf (Host header fuzz)", value="ffuf"),
            Choice("← Back", value=None, shortcut_key="q"),
        ],
        use_shortcuts=True,
    ).ask()
    if tool is None:
        return

    if tool == "gobuster":
        if not require("gobuster", friendly_name="Gobuster").ok:
            pause()
            return
        argv = ["gobuster", "dns", "-d", domain, "-w", wl]
        res = run_with_preview(argv, title="gobuster dns", module_slug="recon_subdomains_gobuster")
        if not res:
            return
        found = [ln for ln in res.output.splitlines() if "Found:" in ln or ln.strip().startswith(domain)]
        scripty_says("If you found subdomains, feed them into web recon and run targeted port scans.")
        if found:
            console.print(Panel(Text("\n".join(found[:80]), style=COLORS.muted), title=Text("Discovered", style=COLORS.primary), border_style=COLORS.primary, box=box.ROUNDED))
        next_steps(["Try `whatweb` / dir busting on discovered hosts.", "Run `nmap -sV -sC` against new IPs/hosts."])
    else:
        if not require("ffuf", friendly_name="ffuf").ok:
            pause()
            return
        url = ask_text("Base URL", default=f"http://{domain}", placeholder="http(s)://example.com")
        if not url:
            return
        argv = ["ffuf", "-w", wl, "-u", url, "-H", f"Host: FUZZ.{domain}", "-fs", "0"]
        res = run_with_preview(argv, title="ffuf subdomains", module_slug="recon_subdomains_ffuf", warning="This is a crude active check. Passive sources can be quieter.")
        if not res:
            return
        scripty_says("ffuf host header fuzzing finished. Look for consistent 200/301/302 responses or unique sizes.")
    pause()


if __name__ == "__main__":
    # Minimal standalone run
    menu(state=SessionState(sticky_target=None), cfg=Config())

