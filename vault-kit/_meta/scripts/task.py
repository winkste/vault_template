#!/usr/bin/env python3
"""Maintains the central task list (tasks_file in _meta/vault.config.json).

All changes run under an exclusive file lock so that agents writing at the
same time never overwrite each other. The human edits the file directly in
Obsidian.

Commands:
  add   add a task under an area (the area heading is created if missing)
  done  mark an open task as done and move it to "Done"
  list  print open tasks

Examples:
  task.py add --area Architecture --text "Document the message bus" \\
              --link architecture-overview --due 2026-10-20 --actor github-copilot
  task.py done --match "message bus" --actor github-copilot
  task.py list --area Architecture --json

Line format (compatible with the Obsidian "Tasks" plugin):
  - [ ] Text – [[link]] 📅 2026-10-20 ➕ 2026-10-07 (github-copilot)
  - [x] [Architecture] Text – [[link]] ➕ 2026-10-07 (github-copilot) ✅ 2026-10-09 (github-copilot)

Exit codes: 0 = ok, 1 = task not found / ambiguous, 2 = usage/file error.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import re
import sys

from vaultlib import ACTOR, NOTE_ID, VAULT, load_config

DONE_HEADING = "## Done"
OPEN = re.compile(r"^- \[ \] (.+)$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def today() -> str:
    return dt.date.today().isoformat()


def sections(lines: list[str]) -> list[tuple[str, int]]:
    return [(l.strip(), i) for i, l in enumerate(lines) if l.startswith("## ")]


def section_end(lines: list[str], start: int) -> int:
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## "):
            return i
    return len(lines)


def open_tasks(lines: list[str]) -> list[dict]:
    result, area = [], None
    for i, line in enumerate(lines):
        if line.startswith("## "):
            area = line[3:].strip()
            continue
        m = OPEN.match(line.rstrip("\n"))
        if m and area and area != DONE_HEADING[3:]:
            result.append({"area": area, "text": m.group(1), "line": i + 1})
    return result


def touch_updated(lines: list[str]) -> None:
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                break
            if lines[i].startswith("updated:"):
                lines[i] = f"updated: {today()}\n"


def cmd_add(lines: list[str], args) -> tuple[str, dict]:
    area = args.area.strip()
    if area.lower() == DONE_HEADING[3:].lower():
        raise ValueError(f"Area '{DONE_HEADING[3:]}' is reserved")
    parts = [args.text.strip()]
    links = [l.strip() for group in args.link for l in group.split(",") if l.strip()]
    for link in links:
        if not NOTE_ID.match(link):
            raise ValueError(f"--link '{link}' is not a note id (kebab-case)")
    if links:
        parts.append("– " + ", ".join(f"[[{l}]]" for l in links))
    if args.due:
        if not DATE.match(args.due):
            raise ValueError("--due must be YYYY-MM-DD")
        parts.append(f"📅 {args.due}")
    parts.append(f"➕ {today()} ({args.actor})")
    entry = "- [ ] " + " ".join(parts) + "\n"

    heading = f"## {area}"
    found = next((i for h, i in sections(lines) if h == heading), None)
    if found is None:
        done_at = next((i for h, i in sections(lines) if h == DONE_HEADING), len(lines))
        lines[done_at:done_at] = [f"{heading}\n", "\n", entry, "\n"]
    else:
        insert = section_end(lines, found)
        while insert > found + 1 and not lines[insert - 1].strip():
            insert -= 1
        lines[insert:insert] = [entry]
    return "added", {"area": area, "entry": entry.rstrip("\n")}


def cmd_done(lines: list[str], args) -> tuple[str, dict]:
    needle = args.match.lower()
    hits = [t for t in open_tasks(lines) if needle in t["text"].lower()]
    if not hits:
        raise LookupError(f"No open task contains '{args.match}'")
    if len(hits) > 1:
        raise LookupError("Ambiguous, please be more specific: " + " | ".join(f"[{h['area']}] {h['text']}" for h in hits))
    task = hits[0]
    del lines[task["line"] - 1]
    entry = f"- [x] [{task['area']}] {task['text']} ✅ {today()} ({args.actor})\n"
    done_at = next((i for h, i in sections(lines) if h == DONE_HEADING), None)
    if done_at is None:
        if lines and lines[-1].strip():
            lines.append("\n")
        lines += [f"{DONE_HEADING}\n", "\n", entry]
    else:
        pos = done_at + 2 if done_at + 1 < len(lines) and not lines[done_at + 1].strip() else done_at + 1
        lines.insert(pos, entry)
    return "done", {"area": task["area"], "entry": entry.rstrip("\n")}


def main() -> int:
    parser = argparse.ArgumentParser(description="Maintains the central task list (with file locking).")
    parser.add_argument("--json", action="store_true", help="Print the result as JSON")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Add a task")
    p_add.add_argument("--area", required=True, help="Section, e.g. Architecture, Operations")
    p_add.add_argument("--text", required=True, help="The task in one line")
    p_add.add_argument("--link", action="append", default=[], help="Note ids, comma-separated; repeatable")
    p_add.add_argument("--due", help="Due date YYYY-MM-DD")
    p_add.add_argument("--actor", required=True, help="Who adds it: human, github-copilot, claude-code, …")

    p_done = sub.add_parser("done", help="Mark a task as done")
    p_done.add_argument("--match", required=True, help="Unique text fragment of the open task")
    p_done.add_argument("--actor", required=True, help="Who completed it")

    p_list = sub.add_parser("list", help="List open tasks")
    p_list.add_argument("--area", help="Only this area")

    args = parser.parse_args()
    for value in vars(args).values():
        values = value if isinstance(value, list) else [value]
        if any(isinstance(v, str) and "\n" in v for v in values):
            print("Values must not contain line breaks.", file=sys.stderr)
            return 2
    if hasattr(args, "actor") and not ACTOR.match(args.actor):
        print(f"--actor '{args.actor}' does not match the actor format.", file=sys.stderr)
        return 2

    tasks_path = VAULT / load_config()["tasks_file"]
    if not tasks_path.exists():
        print(f"Task list missing: {tasks_path}", file=sys.stderr)
        return 2

    mode = "r" if args.cmd == "list" else "r+"
    try:
        with tasks_path.open(mode, encoding="utf-8") as fh:
            fcntl.flock(fh, fcntl.LOCK_SH if mode == "r" else fcntl.LOCK_EX)
            try:
                lines = fh.read().splitlines(keepends=True)
                if args.cmd == "list":
                    tasks = [t for t in open_tasks(lines) if not args.area or t["area"] == args.area]
                    if args.json:
                        print(json.dumps(tasks, ensure_ascii=False, indent=2))
                    else:
                        for t in tasks:
                            print(f"[{t['area']}] {t['text']}")
                        print(f"\n{len(tasks)} open tasks")
                    return 0
                handler = cmd_add if args.cmd == "add" else cmd_done
                action, info = handler(lines, args)
                touch_updated(lines)
                fh.seek(0)
                fh.write("".join(lines))
                fh.truncate()
                fh.flush()
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)
    except (ValueError, LookupError) as exc:
        print(f"task: {exc}", file=sys.stderr)
        return 1 if isinstance(exc, LookupError) else 2
    except OSError as exc:
        print(f"Task list not writable: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"action": action, **info}, ensure_ascii=False))
    else:
        print(f"task {action}: {info['entry']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
