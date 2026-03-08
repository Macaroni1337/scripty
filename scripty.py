from __future__ import annotations

import sys
from typing import Optional

import typer

from core.app import run_interactive


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
    try:
        run_interactive(initial_target=target)
    except KeyboardInterrupt:
        # Always exit cleanly.
        raise typer.Exit(code=130)


if __name__ == "__main__":
    app()

