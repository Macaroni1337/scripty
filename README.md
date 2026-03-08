# Scripty — AI-Assisted CLI Pentest Companion

Scripty is a guided, interactive CLI “mentor” that wraps common pentesting tools (nmap, gobuster, hydra, sqlmap, etc.) with a friendly, snarky UX: menus, prompts, command previews, live output, and plain-English summaries.

## Legal / ethical disclaimer

Scripty is **for authorized testing only**. On first launch you must type `AGREE` to continue.

## Requirements

- Python **3.10+**
- A terminal that supports interactive prompts
- External tools as needed (Kali/Debian recommended). Scripty will check and show what’s missing.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

Interactive:

```bash
python scripty.py
```

Optional flag:

```bash
python scripty.py --target 10.10.10.10
```

## Notes

- Config is stored at `~/.scripty/config.toml`
- Saved scan results go to `~/.scripty/results/`

