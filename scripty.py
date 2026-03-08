from __future__ import annotations

import os
import sys
from typing import Optional

import typer

def _ensure_utf8_stdout() -> None:
    # Windows consoles can default to cp1252 and crash on box-drawing / block chars.
    if os.name != "nt":
        return
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


_ensure_utf8_stdout()

_import_error: Exception | None = None
try:
    from core.app import run_interactive
except ModuleNotFoundError as e:  # pragma: no cover
    # Allow `--help` to work even before deps are installed.
    run_interactive = None  # type: ignore[assignment]
    _import_error = e


app = typer.Typer(
    add_completion=False,
    help="Scripty — pentesting for the rest of us (authorized testing only).",
)


@app.command()
def main(
    target: Optional[str] = typer.Option(
        None,
        "--target",
        "-t",
        help="Pre-fill / set the default target for this session.",
    ),
):
    """Launch the interactive Scripty experience."""
    if run_interactive is None:
        missing = getattr(_import_error, "name", "a dependency")
        typer.echo(f"Missing dependency: {missing}")
        typer.echo("Install deps with: pip install -r requirements.txt")
        raise typer.Exit(code=1)
    try:
        run_interactive(initial_target=target)
    except KeyboardInterrupt:
        # Always exit cleanly.
        raise typer.Exit(code=130)


if __name__ == "__main__":
    app()

