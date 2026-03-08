from __future__ import annotations

from pathlib import Path

import questionary
from questionary import Choice
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from core.config import Config, load_config, save_config
from core.dependency_check import check_all, render_dependency_table
from core.install_tools import get_installable_missing, run_install
from core.paths import get_paths
from core.state import SessionState
from core.theme import COLORS
from core.ui import ask_text, pause
from core.wordlists import load_wordlists, resolve_wordlist_path
from modules._shared import header, scripty_says


console = Console()


def set_default_target(*, state: SessionState, cfg: Config) -> Config:
    header("Toolkit & Settings", "Set a default target so you stop retyping. Scripty will still let you override per module.")
    t = ask_text("Default target", default=cfg.default_target or state.sticky_target or "", placeholder="10.10.10.10", validate_non_empty=False)
    if t is None:
        return cfg
    t = t.strip() or None
    state.sticky_target = t
    new_cfg = cfg.with_updates(default_target=t)
    save_config(new_cfg)
    scripty_says(f"Default target set to: {t or '(none)'}")
    pause()
    return new_cfg


def set_default_wordlist(*, cfg: Config) -> Config:
    header("Toolkit & Settings", "Set a default wordlist path used by multiple modules.")
    default = resolve_wordlist_path(cfg.default_wordlist)
    choices = [Choice(f"{wl.name}  ({wl.path})", value=wl.path) for wl in load_wordlists()]
    choices += [Choice("Custom path…", value="custom"), Choice("Clear default", value="clear"), Choice("← Back", value=None)]
    sel = questionary.select("Default wordlist", choices=choices, instruction="Ctrl+C to go back.").ask()
    if sel is None:
        return cfg
    if sel == "custom":
        p = ask_text("Wordlist path", default=default or "", placeholder="/usr/share/wordlists/rockyou.txt")
        if not p:
            return cfg
        sel = p.strip()
    if sel == "clear":
        sel = None
    new_cfg = cfg.with_updates(default_wordlist=sel)
    save_config(new_cfg)
    scripty_says(f"Default wordlist set to: {sel or '(none)'}")
    pause()
    return new_cfg


def set_output_dir(*, cfg: Config) -> Config:
    header("Toolkit & Settings", "Set a default output directory for saved results (optional).")
    p = ask_text("Default output directory", default=cfg.default_output_dir or "", placeholder="~/pentest-results", validate_non_empty=False)
    if p is None:
        return cfg
    p = p.strip() or None
    new_cfg = cfg.with_updates(default_output_dir=p)
    save_config(new_cfg)
    scripty_says(f"Default output dir set to: {p or '(none)'}")
    pause()
    return new_cfg


def view_config() -> None:
    header("Toolkit & Settings", "Your config lives at ~/.scripty/config.toml. If you break it, Scripty will try not to cry.")
    paths = get_paths()
    if not paths.config_path.exists():
        _ = load_config()
    try:
        content = paths.config_path.read_text(encoding="utf-8")
    except Exception:
        content = "(unable to read config)"
    console.print(
        Panel(
            Text(content, style=COLORS.muted),
            title=Text(str(paths.config_path), style=COLORS.primary),
            border_style=COLORS.primary,
            box=box.ROUNDED,
        )
    )
    pause()


def tool_check() -> None:
    header("Toolkit & Settings", "Dependency check. Missing tools won’t crash Scripty — but they will limit what you can run.")
    rows = check_all()
    if rows:
        console.print(render_dependency_table(rows))
        installable = get_installable_missing()
        if installable:
            try:
                do_install = questionary.confirm(
                    "Install missing tools now? (apt on Linux, Homebrew on macOS)",
                    default=False,
                ).ask()
            except KeyboardInterrupt:
                do_install = False
            if do_install:
                run_install()
    else:
        console.print(Panel.fit(Text("No tool metadata found.", style=COLORS.warning), border_style=COLORS.warning, box=box.ROUNDED))
    pause()


def about(cfg: Config) -> None:
    header("Toolkit & Settings", "About Scripty")
    lines = [
        f"Version: {cfg.version}",
        "Tone: snarky mentor in your terminal.",
        "Purpose: guide authorized security testing with command previews and human summaries.",
        "",
        "Credits: built with Rich + Questionary + Typer.",
    ]
    console.print(Panel(Text("\n".join(lines), style=COLORS.muted), border_style=COLORS.primary, box=box.ROUNDED))
    pause()


def menu(*, state: SessionState, cfg: Config) -> None:
    while True:
        header("Toolkit & Settings", "Configure Scripty, manage wordlists, view config, and re-run dependency checks.")
        try:
            sel = questionary.select(
                "Pick a settings action",
                choices=[
                    Choice("Set default target", value="target"),
                    Choice("Set default wordlist", value="wordlist"),
                    Choice("Set default output directory", value="outdir"),
                    Choice("View config file", value="config"),
                    Choice("Check for missing tools", value="tools"),
                    Choice("Install missing tools (apt / Homebrew)", value="install_tools"),
                    Choice("About", value="about"),
                    Choice("← Back", value=None, shortcut_key="q"),
                ],
                instruction="Ctrl+C to go back.",
                use_shortcuts=True,
            ).ask()
        except KeyboardInterrupt:
            return
        if sel is None:
            return
        if sel == "target":
            cfg = set_default_target(state=state, cfg=cfg)
        elif sel == "wordlist":
            cfg = set_default_wordlist(cfg=cfg)
        elif sel == "outdir":
            cfg = set_output_dir(cfg=cfg)
        elif sel == "config":
            view_config()
        elif sel == "tools":
            tool_check()
        elif sel == "install_tools":
            run_install()
            pause()
        elif sel == "about":
            about(cfg)


if __name__ == "__main__":
    menu(state=SessionState(sticky_target=None), cfg=Config())

