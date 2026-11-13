#!/usr/bin/env python3
"""
Project log maintenance script.
Shared between Executor (read+write) and Verifier (read-only).
"""
import os, sys
from datetime import datetime, date
from pathlib import Path
from typing import Optional

LOG_DIR = Path(__file__).resolve().parent


def init():
    """Ensure log/ directory exists. Create today's log with header if missing."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    today_path = LOG_DIR / f"{date.today().isoformat()}.md"
    if not today_path.exists():
        today_path.write_text(
            f"# Project Log 鈥?{date.today().isoformat()}\n\n"
            f"## Initialized\n\n"
        )
    return today_path


def _today_path() -> Path:
    return LOG_DIR / f"{date.today().isoformat()}.md"


def add(message: str, change_type: str = "", rationale: str = ""):
    """
    Append a log entry to today's file.

    Args:
        message:  What was done (short, one sentence).
        change_type:  "config" | "adapter" | "harness" | "experiment" | "doc" | "skill"
        rationale:  If this replaces a previous approach (even a small scope),
                    explain why. Can be empty for first-time additions.
    """
    init()
    now = datetime.now().strftime("%H:%M")
    lines = [f"## [{now}]"]
    if change_type:
        lines[0] += f" [{change_type}]"
    lines[0] += f" {message}"
    if rationale:
        lines.append(f"  - 鍘熷洜: {rationale}")
    lines.append("")
    text = "\n".join(lines)

    path = _today_path()
    with open(path, "a") as f:
        f.write(text + "\n")

    print(f"[log] {text.split(chr(10))[0]}")


def scan(lines: int = 30) -> str:
    """
    Return the last N lines from the most recent log files.
    Merges today's log + yesterday's if today is short.
    """
    init()
    today = _today_path()

    all_lines = []
    if today.exists():
        all_lines = today.read_text().strip().split("\n")

    # If today has fewer than `lines` entries, pull from yesterday
    if len(all_lines) < lines:
        yesterday_path = LOG_DIR / Path(
            date.today().isoformat().rsplit("-", 1)[0]
            + "-"
            + str(max(1, int(date.today().day) - 1)).zfill(2)
        ).with_suffix(".md")
        # Actually just use a simple approach: find the second most recent file
        log_files = sorted(LOG_DIR.glob("*.md"), reverse=True)
        if len(log_files) > 1:
            prev = log_files[1]
            prev_lines = prev.read_text().strip().split("\n")
            all_lines = prev_lines[-lines:] + all_lines

    return "\n".join(all_lines[-lines:])


def today() -> str:
    """Return the full text of today's log."""
    path = _today_path()
    if path.exists():
        return path.read_text()
    return ""


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["add", "scan", "today"])
    parser.add_argument("--message", "-m", default="", help="log message")
    parser.add_argument("--type", "-t", default="")
    parser.add_argument("--rationale", "-r", default="")
    parser.add_argument("-n", "--lines", type=int, default=30)
    args = parser.parse_args()

    if args.action == "add":
        add(args.message, args.type, args.rationale)
    elif args.action == "scan":
        print(scan(args.lines))
    elif args.action == "today":
        print(today())