from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

import questionary
from questionary import Choice
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from core.config import Config
from core.config import save_config
from core.state import SessionState
from core.theme import COLORS
from core.tools import require
from core.ui import ask_text, pause
from core.wordlists import load_wordlists, resolve_wordlist_path
from modules._shared import header, next_steps, run_with_preview, scripty_says


console = Console()


def _pick_wordlist(cfg: Config, purpose: str) -> Optional[str]:
    default = resolve_wordlist_path(cfg.default_wordlist)
    choices = [Choice(f"{wl.name}  ({wl.path})", value=wl.path) for wl in load_wordlists()]
    choices += [Choice("Custom path…", value="custom"), Choice("← Back", value=None)]
    sel = questionary.select(f"Wordlist for {purpose}", choices=choices, instruction="Ctrl+C to go back.").ask()
    if sel is None:
        return None
    if sel == "custom":
        p = ask_text("Wordlist path", default=default or "", placeholder="/usr/share/wordlists/rockyou.txt")
        return p.strip() if p else None
    return sel


def hydra_bruteforce(*, state: SessionState, cfg: Config) -> None:
    header("Password Attacks", "Hydra brute forces logins. Use only with permission and sane rate limits.")
    if not require("hydra", friendly_name="Hydra").ok:
        pause()
        return

    target = ask_text("Target IP/host", default=state.sticky_target or "", placeholder="10.10.10.10")
    if not target:
        return
    state.sticky_target = target.strip()

    service = questionary.select(
        "Service",
        choices=[
            Choice("ssh", value="ssh"),
            Choice("ftp", value="ftp"),
            Choice("smb", value="smb"),
            Choice("rdp", value="rdp"),
            Choice("http-post-form (guided)", value="http-post-form"),
            Choice("Custom…", value="custom"),
            Choice("← Back", value=None),
        ],
    ).ask()
    if service is None:
        return
    if service == "custom":
        service = ask_text("Hydra service module", default="ssh", placeholder="Example: ssh / ftp / http-get / http-post-form") or ""
        service = service.strip()
        if not service:
            return

    user = ask_text("Username (single) (leave blank to use list)", default="", placeholder="admin", validate_non_empty=False) or ""
    userlist = ""
    if not user.strip():
        userlist = ask_text("Username list path", default="", placeholder="/path/to/users.txt")
        if not userlist:
            return

    passlist = _pick_wordlist(cfg, "password brute force")
    if not passlist:
        return

    extra: List[str] = []
    if service == "http-post-form":
        login_path = ask_text("Login path (relative)", default="/login", placeholder="/login or /wp-login.php") or "/login"
        post_body = ask_text(
            "POST body template",
            default="username=^USER^&password=^PASS^",
            placeholder="Use ^USER^ and ^PASS^ placeholders",
        )
        fail = ask_text("Failure string (text that indicates bad login)", default="Invalid", placeholder="Example: Invalid password")
        if not post_body or not fail:
            return
        form = f"{login_path}:{post_body}:{fail}"
        extra = ["-V", "-f", "-s", "80", state.sticky_target, "http-post-form", form]
        argv = ["hydra"]
        if user.strip():
            argv += ["-l", user.strip()]
        else:
            argv += ["-L", userlist]
        argv += ["-P", passlist] + extra
    else:
        argv = ["hydra"]
        if user.strip():
            argv += ["-l", user.strip()]
        else:
            argv += ["-L", userlist]
        argv += ["-P", passlist, service, state.sticky_target]

    res = run_with_preview(argv, title="hydra", module_slug="pw_hydra", warning="Brute forcing can lock accounts and trigger alerts. Use rate limits and permission.")
    if not res:
        return

    hits = [ln for ln in res.output.splitlines() if "login:" in ln.lower() and "password:" in ln.lower()]
    if hits:
        scripty_says("Found potential credentials. Verify them manually; false positives happen.")
        console.print(Panel(Text("\n".join(hits[:30]), style=COLORS.success), title=Text("Hits", style=COLORS.success), border_style=COLORS.success, box=box.ROUNDED))
        next_steps(["Try the creds on the real service (ssh/smb/http).", "If valid → pivot to post-exploitation enumeration."])
    else:
        scripty_says("No creds found in parsed output. Consider different wordlists/usernames or confirm the service is reachable.")
    pause()


def john_crack() -> None:
    header("Password Attacks", "John cracks hashes. Feed it good wordlists and realistic expectations.")
    if not require("john", friendly_name="John the Ripper").ok:
        pause()
        return
    hash_file = ask_text("Hash file path", default="", placeholder="/tmp/hashes.txt")
    if not hash_file:
        return
    wl = ask_text("Wordlist path (optional)", default="", placeholder="/usr/share/wordlists/rockyou.txt", validate_non_empty=False) or ""
    fmt = ask_text("Format (optional)", default="", placeholder="leave blank for auto", validate_non_empty=False) or ""
    argv = ["john"]
    if wl.strip():
        argv += [f"--wordlist={wl.strip()}"]
    if fmt.strip():
        argv += [f"--format={fmt.strip()}"]
    argv += [hash_file]
    res = run_with_preview(argv, title="john", module_slug="pw_john", warning="This can take a while. Ctrl+C stops, but results may still be showable.")
    if not res:
        return
    show = run_with_preview(["john", "--show", hash_file], title="john --show", module_slug="pw_john_show")
    if show and show.output.strip():
        scripty_says("Cracked creds (if any) are shown below.")
        console.print(Panel(Text(show.output.strip()[:4000], style=COLORS.muted), title=Text("john --show", style=COLORS.primary), border_style=COLORS.primary, box=box.ROUNDED))
    pause()


def hashcat_run() -> None:
    header("Password Attacks", "Hashcat is fast. Your GPU and time are the limiters. Choose modes wisely.")
    if not require("hashcat", friendly_name="Hashcat").ok:
        pause()
        return
    target = ask_text("Hash or hash file path", default="", placeholder="Either paste a hash or provide /path/to/hashes.txt")
    if not target:
        return
    mode = ask_text("Hash type (-m)", default="0", placeholder="Example: 0 (MD5), 1000 (NTLM)", validate_non_empty=False) or "0"
    attack = questionary.select(
        "Attack mode",
        choices=[
            Choice("Wordlist (-a 0)", value="wordlist"),
            Choice("Brute force mask (-a 3)", value="mask"),
            Choice("← Back", value=None, shortcut_key="q"),
        ],
        use_shortcuts=True,
    ).ask()
    if attack is None:
        return

    argv = ["hashcat", "-m", mode.strip()]
    if attack == "wordlist":
        wl = ask_text("Wordlist path", default="", placeholder="/usr/share/wordlists/rockyou.txt")
        if not wl:
            return
        argv += ["-a", "0", target, wl]
    else:
        mask = ask_text("Mask", default="?a?a?a?a?a?a?a?a", placeholder="Example: ?l?l?l?l?l?l?l?l")
        if not mask:
            return
        argv += ["-a", "3", target, mask]

    res = run_with_preview(argv, title="hashcat", module_slug="pw_hashcat", warning="Hashcat can peg your GPU/CPU. Monitor thermals.")
    if not res:
        return
    scripty_says("If you cracked anything, run `hashcat --show ...` with the same args to display results.")
    pause()


def hash_identifier() -> None:
    header("Password Attacks", "Hash ID is guesswork with math. Still useful for narrowing options.")
    h = ask_text("Paste a hash", default="", placeholder="e.g. 5f4dcc3b5aa765d61d8327deb882cf99")
    if not h:
        return
    h = h.strip()
    candidates: List[str] = []

    if re.fullmatch(r"[a-fA-F0-9]{32}", h):
        candidates += ["MD5 (32 hex)"]
    if re.fullmatch(r"[a-fA-F0-9]{40}", h):
        candidates += ["SHA1 (40 hex)"]
    if re.fullmatch(r"[a-fA-F0-9]{64}", h):
        candidates += ["SHA-256 (64 hex)"]
    if h.startswith("$2a$") or h.startswith("$2b$") or h.startswith("$2y$"):
        candidates += ["bcrypt ($2y$...)"]
    if h.startswith("$6$"):
        candidates += ["SHA-512 crypt ($6$...)"]
    if h.startswith("$1$"):
        candidates += ["MD5 crypt ($1$...)"]
    if h.upper().startswith("NTLM") or re.fullmatch(r"[A-F0-9]{32}", h) and h.isupper():
        candidates += ["Possibly NTLM (also 32 hex; verify context)"]

    if candidates:
        t = Table(title="Likely candidates (best-effort)", box=box.SIMPLE_HEAVY)
        t.add_column("Candidate", style=COLORS.primary)
        for c in candidates[:10]:
            t.add_row(c)
        console.print(t)
        scripty_says("Use context (source system/app) to confirm. Then pick John/Hashcat formats/modes accordingly.")
    else:
        scripty_says("Couldn’t confidently identify that hash by simple patterns. Use `hashid`/`hash-identifier` on Kali for better guesses.")
    pause()


def wordlist_manager(*, cfg: Config) -> Config:
    header("Password Attacks", "Wordlists: boring file, exciting outcomes. Set a default so you stop retyping paths.")
    known = load_wordlists()
    choices = [Choice(f"{wl.name}  ({wl.path})", value=wl.path) for wl in known]
    choices += [Choice("Custom path…", value="custom"), Choice("← Back", value=None)]
    sel = questionary.select("Set default wordlist", choices=choices, instruction="Ctrl+C to go back.").ask()
    if sel is None:
        return cfg
    if sel == "custom":
        p = ask_text("Default wordlist path", default=cfg.default_wordlist or "", placeholder="/usr/share/wordlists/rockyou.txt")
        if not p:
            return cfg
        sel = p.strip()
    new_cfg = cfg.with_updates(default_wordlist=sel)
    save_config(new_cfg)
    scripty_says(f"Default wordlist set to: {sel}")
    pause()
    return new_cfg


def menu(*, state: SessionState, cfg: Config) -> None:
    while True:
        header("Password Attacks", "Brute force, wordlists, hash cracking. Be careful: these actions are noisy.")
        try:
            sel = questionary.select(
                "Pick a password action",
                choices=[
                    Choice("4.1 Hydra — Brute Force Login", value="hydra"),
                    Choice("4.2 John the Ripper", value="john"),
                    Choice("4.3 Hashcat", value="hashcat"),
                    Choice("4.4 Hash Identifier", value="hashid"),
                    Choice("4.5 Wordlist Manager", value="wordlists"),
                    Choice("← Back", value=None, shortcut_key="q"),
                ],
                instruction="Ctrl+C to go back.",
                use_shortcuts=True,
            ).ask()
        except KeyboardInterrupt:
            return

        if sel is None:
            return
        if sel == "hydra":
            hydra_bruteforce(state=state, cfg=cfg)
        elif sel == "john":
            john_crack()
        elif sel == "hashcat":
            hashcat_run()
        elif sel == "hashid":
            hash_identifier()
        elif sel == "wordlists":
            cfg = wordlist_manager(cfg=cfg)


if __name__ == "__main__":
    menu(state=SessionState(sticky_target=None), cfg=Config())

