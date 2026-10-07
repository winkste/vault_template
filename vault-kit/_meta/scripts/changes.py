#!/usr/bin/env python3
"""Deterministically reports new, changed and deleted sources in the raw folder.

Compares the current content of raw_dir (SHA-256 per file) with the manifest
_meta/state/raw-manifest.json. No LLM is called – the script only says *what*
has changed.

Typical flow:
  changes.py            # what is new/changed/deleted?
  ... process the sources ...
  changes.py --update   # record the processed state in the manifest

Exit codes: 0 = ok (or no changes with --exit-code),
            1 = changes present (only with --exit-code), 2 = error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys

from vaultlib import VAULT, load_config

MANIFEST = VAULT / "_meta" / "state" / "raw-manifest.json"
MANIFEST_VERSION = 1
IGNORE_NAMES = {".DS_Store"}
IGNORE_REL = {"README.md"}  # the folder README is not a source


def sha256(path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan(raw) -> dict[str, dict]:
    files: dict[str, dict] = {}
    for path in sorted(raw.rglob("*")):
        if not path.is_file() or path.name in IGNORE_NAMES:
            continue
        rel = path.relative_to(raw).as_posix()
        if rel in IGNORE_REL or any(p.startswith(".") for p in path.relative_to(raw).parts):
            continue
        files[rel] = {"sha256": sha256(path), "size": path.stat().st_size}
    return files


def load_manifest() -> dict[str, dict]:
    if not MANIFEST.exists():
        return {}
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data.get("manifest_version") != MANIFEST_VERSION:
        raise ValueError(f"Unknown manifest_version in {MANIFEST}")
    return data.get("files", {})


def write_manifest(files: dict[str, dict], root: str) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    payload = {"manifest_version": MANIFEST_VERSION, "root": root, "files": files}
    MANIFEST.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Lists new/changed/deleted files in the raw folder compared to the hash manifest.")
    parser.add_argument("--json", action="store_true", help="Print the result as JSON")
    parser.add_argument("--update", action="store_true", help="Set the manifest to the current state (after processing)")
    parser.add_argument("--exit-code", action="store_true", help="Exit code 1 if there are changes (like git diff --exit-code)")
    args = parser.parse_args()

    root = load_config()["raw_dir"]
    raw = VAULT / root
    if not raw.is_dir():
        print(f"Folder missing: {raw}", file=sys.stderr)
        return 2
    try:
        old = load_manifest()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Manifest not readable: {exc}", file=sys.stderr)
        return 2

    current = scan(raw)
    added = sorted(set(current) - set(old))
    deleted = sorted(set(old) - set(current))
    modified = sorted(k for k in set(current) & set(old) if current[k]["sha256"] != old[k]["sha256"])
    unchanged = len(current) - len(added) - len(modified)
    has_changes = bool(added or modified or deleted)

    if args.update:
        write_manifest(current, root)

    prefix = root + "/"
    if args.json:
        print(json.dumps({"added": [prefix + p for p in added], "modified": [prefix + p for p in modified],
                          "deleted": [prefix + p for p in deleted], "unchanged": unchanged,
                          "manifest_updated": args.update}, ensure_ascii=False, indent=2))
    else:
        for label, items in (("NEW", added), ("CHANGED", modified), ("DELETED", deleted)):
            for p in items:
                print(f"{label:8} {prefix}{p}")
        summary = f"{len(added)} new, {len(modified)} changed, {len(deleted)} deleted, {unchanged} unchanged"
        print(("\n" if has_changes else "") + "changes: " + summary + (" – manifest updated" if args.update else ""))
    return 1 if (args.exit_code and has_changes) else 0


if __name__ == "__main__":
    sys.exit(main())
