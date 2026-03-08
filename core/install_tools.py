"""Install missing tools via apt (Linux) or brew (macOS)."""
from __future__ import annotations

import platform
from typing import List, Optional, Tuple

import questionary
from questionary import Choice
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from core.dependency_check import ToolInfo, check_all
from core.runner import run_streaming
from core.theme import COLORS


console = Console()


def _platform() -> str:
    return platform.system().lower()


def _apt_package(apt_cmd: Optional[str]) -> Optional[str]:
    """Extract package name from 'sudo apt install -y <pkg>'."""
    if not apt_cmd:
        return None
    parts = apt_cmd.split()
    for i in range(len(parts) - 1, -1, -1):
        if not parts[i].startswith("-"):
            return parts[i]
    return None


def _brew_package(brew_cmd: Optional[str]) -> Optional[str]:
    """Extract package name from 'brew install <pkg>'."""
    if not brew_cmd:
        return None
    parts = brew_cmd.split()
    if "install" in parts:
        idx = parts.index("install") + 1
        if idx < len(parts):
            return parts[idx]
    return None


def get_missing_tools() -> List[ToolInfo]:
    """Return ToolInfo list for tools that are not on PATH."""
    rows = check_all()
    return [info for info, ok, _ in rows if not ok]


def get_installable_missing() -> List[Tuple[ToolInfo, str, str]]:
    """
    Return (ToolInfo, package_name, manager) for missing tools we can install.
    manager is 'apt' or 'brew'.
    """
    missing = get_missing_tools()
    plat = _platform()
    result: List[Tuple[ToolInfo, str, str]] = []
    for t in missing:
        if plat == "linux" and t.apt:
            pkg = _apt_package(t.apt)
            if pkg:
                result.append((t, pkg, "apt"))
        elif plat == "darwin" and t.brew:
            pkg = _brew_package(t.brew)
            if pkg:
                result.append((t, pkg, "brew"))
    return result


def build_install_commands(installable: List[Tuple[ToolInfo, str, str]]) -> Optional[Tuple[str, List[List[str]]]]:
    """
    For current platform, build (description, list of argv) from installable list.
    Returns None if empty or platform has no supported installer.
    """
    if not installable:
        return None
    plat = _platform()
    if plat == "linux":
        pkgs = [pkg for _, pkg, m in installable if m == "apt"]
        if not pkgs:
            return None
        return (
            "apt (Debian/Kali)",
            [
                ["sudo", "apt", "update"],
                ["sudo", "apt", "install", "-y"] + pkgs,
            ],
        )
    if plat == "darwin":
        pkgs = [pkg for _, pkg, m in installable if m == "brew"]
        if not pkgs:
            return None
        return ("Homebrew", [["brew", "install"] + pkgs])
    return None


def run_install(choice: Optional[List[ToolInfo]] = None) -> bool:
    """
    Let user install missing tools. If choice is None, install all installable.
    If choice is a list, only those tools (must be missing and installable).
    Returns True if install was run, False if skipped/cancelled.
    """
    plat = _platform()
    if plat == "windows":
        console.print(
            Panel(
                Text(
                    "Auto-install is supported on Linux (apt) and macOS (Homebrew).\n\n"
                    "On Windows use WSL with apt, or install tools manually (e.g. winget, Chocolatey).\n"
                    "The dependency table shows install hints for each tool.",
                    style=COLORS.warning,
                ),
                title=Text("Install on Windows", style=COLORS.warning),
                border_style=COLORS.warning,
            )
        )
        return False

    if choice is not None:
        installable = []
        for t in choice:
            pkg_apt = _apt_package(t.apt) if plat == "linux" else None
            pkg_brew = _brew_package(t.brew) if plat == "darwin" else None
            pkg = pkg_apt or pkg_brew
            m = "apt" if (plat == "linux" and t.apt) else ("brew" if (plat == "darwin" and t.brew) else None)
            if pkg and m:
                installable.append((t, pkg, m))
    else:
        installable = get_installable_missing()
        if len(installable) > 1:
            try:
                sel = questionary.select(
                    "What to install?",
                    choices=[
                        Choice("Install all missing tools", value="all"),
                        Choice("Pick specific tools…", value="pick"),
                        Choice("← Back", value=None),
                    ],
                    instruction="Ctrl+C to go back.",
                ).ask()
            except KeyboardInterrupt:
                return False
            if sel is None:
                return False
            if sel == "pick":
                chosen = questionary.checkbox(
                    "Select tools to install",
                    choices=[Choice(f"{info.name} ({info.binary})", value=info) for info, _pkg, _m in installable],
                    instruction="Space to toggle, Enter to confirm.",
                ).ask()
                if not chosen:
                    return False
                return run_install(choice=chosen)
            # "all" -> keep installable as-is
        # single tool or "all" selected
    if not installable:
        console.print(
            Panel.fit(
                Text("No missing tools, or none have apt/brew install commands.", style=COLORS.primary),
                border_style=COLORS.primary,
            )
        )
        return False

    built = build_install_commands(installable)
    if not built:
        return False
    desc, argv_list = built

    preview_lines = [f"# {desc}", ""]
    for argv in argv_list:
        preview_lines.append(" ".join(argv))
    console.print(
        Panel(
            Text("\n".join(preview_lines), style=COLORS.muted),
            title=Text("Command(s) to run", style=COLORS.primary),
            border_style=COLORS.primary,
        )
    )
    try:
        do = questionary.confirm("Run these commands now? (may prompt for sudo)", default=True).ask()
    except KeyboardInterrupt:
        return False
    if not do:
        return False

    for argv in argv_list:
        res = run_streaming(argv, title=" ".join(argv[:3]) + (" …" if len(argv) > 3 else ""))
        if res.exit_code != 0:
            console.print(
                Panel.fit(
                    Text(f"Command failed with exit code {res.exit_code}. Fix any errors above and try again.", style=COLORS.error),
                    border_style=COLORS.error,
                )
            )
            return True  # we did run something
    console.print(
        Panel.fit(
            Text("Done. Run 'Check for missing tools' again to confirm.", style=COLORS.success),
            title=Text("Install finished", style=COLORS.success),
            border_style=COLORS.success,
        )
    )
    return True
