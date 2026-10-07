#!/usr/bin/env python3
"""Appends an entry to the agent log <log_dir>/<YYYY-MM-DD>.md.

Appending happens under an exclusive file lock so that agents writing at the
same time never lose entries. If the daily file is missing, it is created with
valid frontmatter.

Example:
  log.py --actor claude-code --by claude-code/<model> \\
         --title "Architecture notes created" --changed architecture-overview,moc-architecture \\
         --reason "Request by the human"

Entry:
  ## 14:32 [claude-code] Architecture notes created
  - Changed: [[architecture-overview]], [[moc-architecture]]
  - Reason: Request by the human

Exit codes: 0 = ok, 2 = usage/file error.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import sys

from vaultlib import ACTOR, NOTE_ID, VAULT, load_config, owner_of


def format_ref(item: str) -> str:
    """Note ids become wikilinks, anything else (paths, file names) code."""
    item = item.strip()
    if item.startswith("[["):
        return item
    return f"[[{item}]]" if NOTE_ID.match(item) else f"`{item}`"


def frontmatter(day: str, owner: str, by: str, now: dt.datetime, sensitivity: str) -> str:
    return (
        "---\n"
        f"id: {day}\n"
        f"title: Agent log {day}\n"
        f"description: Log of agent changes on {day}.\n"
        "type: log\n"
        "status: stable\n"
        f"sensitivity: {sensitivity}\n"
        f"owner: {owner}\n"
        "tags: [log]\n"
        "generated:\n"
        f"  by: {by}\n"
        f"  at: {now.isoformat(timespec='seconds')}\n"
        f"created: {day}\n"
        f"updated: {day}\n"
        "---\n\n"
        f"# Agent log {day}\n"
    )


def build_entry(args, now: dt.datetime) -> str:
    lines = [f"## {now:%H:%M} [{args.actor}] {args.title}"]
    changed = [c for group in args.changed for c in group.split(",") if c.strip()]
    if changed:
        lines.append("- Changed: " + ", ".join(format_ref(c) for c in changed))
    for detail in args.detail:
        lines.append(f"- {detail}")
    if args.reason:
        lines.append(f"- Reason: {args.reason}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Appends an entry to the daily agent log (with file locking).")
    parser.add_argument("--actor", required=True, help="Who writes: e.g. claude-code, github-copilot, human:<id>")
    parser.add_argument("--by", help="Actor for generated.by of a new daily file (e.g. claude-code/<model>); default: --actor")
    parser.add_argument("--title", required=True, help="Short description (one line)")
    parser.add_argument("--changed", action="append", default=[], help="Changed notes (ids) or paths, comma-separated; repeatable")
    parser.add_argument("--detail", action="append", default=[], help="Additional line, e.g. 'Sources: …'; repeatable")
    parser.add_argument("--reason", help="Reason or request")
    parser.add_argument("--json", action="store_true", help="Print the result as JSON")
    args = parser.parse_args()

    for value in [args.title, args.reason or "", *args.changed, *args.detail]:
        if "\n" in value:
            print("Values must not contain line breaks.", file=sys.stderr)
            return 2
    by = args.by or args.actor
    for name, value in (("--actor", args.actor), ("--by", by)):
        if not ACTOR.match(value):
            print(f"{name} '{value}' does not match the actor format (see _meta/okf-mapping.md).", file=sys.stderr)
            return 2

    config = load_config()
    log_dir = VAULT / config["log_dir"]
    now = dt.datetime.now().astimezone()
    day = now.strftime("%Y-%m-%d")
    path = log_dir / f"{day}.md"
    entry = build_entry(args, now)

    try:
        log_dir.mkdir(exist_ok=True)
        with path.open("a+", encoding="utf-8") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                fh.seek(0)
                existing = fh.read()
                if not existing.strip():
                    prefix = frontmatter(day, owner_of(by, config["owners"]), by, now, config["default_sensitivity"]) + "\n"
                elif existing.endswith("\n\n"):
                    prefix = ""
                elif existing.endswith("\n"):
                    prefix = "\n"
                else:
                    prefix = "\n\n"
                fh.write(prefix + entry)
                fh.flush()
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)
    except OSError as exc:
        print(f"Log not writable ({path}): {exc}", file=sys.stderr)
        return 2

    rel = path.relative_to(VAULT).as_posix()
    if args.json:
        print(json.dumps({"path": rel, "created": not existing.strip(), "entry": entry}, ensure_ascii=False))
    else:
        print(f"log: entry appended to {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
