#!/usr/bin/env python3
"""Validates the knowledge vault against the rules in _meta/CONVENTIONS.md.

Checks:
  - frontmatter against _meta/schema/frontmatter.schema.json
    (enums for 'sensitivity' and 'owner' come from _meta/vault.config.json)
  - id = file name, id unique within the vault
  - file names (kebab-case ASCII; logs YYYY-MM-DD, ADRs adr-NNNN-...)
  - sensitivity never looser than the folder default
  - folder-specific rules (folder_types, decisions/, 99_archive/)
  - broken [[wikilinks]]
  - common secret patterns

Default: the whole vault (working tree). With --staged only the staged files in
their staged version - unfinished, unstaged notes then never block a commit.
Links and ids are checked against the git index in that mode.
Limitation: if a commit deletes a note that other notes link to, only the full
run reports the broken links.

Paths and details from the restricted folder are masked in the output
(unless --show-private), so the output may be passed to cloud-backed agents.

Exit codes: 0 = ok, 1 = errors found, 2 = usage/environment error.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    import jsonschema
    import yaml
except ImportError as exc:  # pragma: no cover
    print(
        f"Missing dependency '{exc.name}'. Setup: "
        "python3 -m venv .venv && .venv/bin/pip install -r _meta/scripts/requirements.txt",
        file=sys.stderr,
    )
    sys.exit(2)

from vaultlib import VAULT, load_config

SCHEMA_PATH = VAULT / "_meta" / "schema" / "frontmatter.schema.json"

# Top-level folders that do not contain notes.
SKIP_TOP = {"_meta", ".git", ".venv", ".obsidian", ".claude", ".github", ".trash"}
# Files without mandatory frontmatter.
EXEMPT_NAMES = {"README.md"}
EXEMPT_ROOT = {"CLAUDE.md", "AGENTS.md"}

KEBAB_MD = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
KEBAB_ANY = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:\.[a-z0-9]+)+$")
LOG_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")
ADR_NAME = re.compile(r"^adr-\d{4}(?:-[a-z0-9]+)+\.md$")
WIKILINK = re.compile(r"!?\[\[([^\]\|#\^]*)(?:[#\^][^\]\|]*)?(?:\|[^\]]*)?\]\]")
FENCE = re.compile(r"^(```|~~~).*?^\1\s*$", re.M | re.S)
INLINE_CODE = re.compile(r"`[^`\n]*`")

TEXT_EXT = {".md", ".txt", ".json", ".yaml", ".yml", ".csv", ".toml", ".ini", ".conf", ".env"}
SECRET_SKIP = ("_meta/scripts/", "_meta/state/", ".git/", ".venv/")
SECRET_ALLOW = "validate:allow-secret"
SECRET_PATTERNS = [
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("api-key", re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{20,}")),
    ("aws-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "credential-assignment",
        re.compile(r"(?i)\b(api[_-]?key|secret|token|passwor[dt]|passwd|pwd)\b\s*[:=]\s*[\"']?[^\s\"'#]{8,}"),
    ),
]
IP_PORT = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}\b")


class Report:
    def __init__(self, show_private: bool, restricted: str) -> None:
        self.show_private = show_private
        self.restricted = restricted
        self.findings: list[dict] = []
        self.files_checked = 0

    def is_private(self, rel: str) -> bool:
        return bool(self.restricted) and rel.startswith(self.restricted) and rel != self.restricted + "README.md"

    def display(self, rel: str) -> str:
        if self.is_private(rel) and not self.show_private:
            return self.restricted + "<" + hashlib.sha1(rel.encode()).hexdigest()[:10] + ">"
        return rel

    def add(self, level, code, rel, message, line=None, private_message=None) -> None:
        if self.is_private(rel) and not self.show_private:
            message = private_message or f"Rule '{code}' violated (details masked)"
        self.findings.append({"level": level, "code": code, "path": self.display(rel), "line": line, "message": message})

    def error(self, *a, **kw) -> None:
        self.add("error", *a, **kw)

    def warn(self, *a, **kw) -> None:
        self.add("warning", *a, **kw)

    @property
    def errors(self) -> int:
        return sum(f["level"] == "error" for f in self.findings)

    @property
    def warnings(self) -> int:
        return sum(f["level"] == "warning" for f in self.findings)


class WorkingTree:
    """The whole vault as it is on disk."""

    def __init__(self) -> None:
        self.all_files = sorted(
            p.relative_to(VAULT).as_posix() for p in VAULT.rglob("*")
            if p.is_file() and p.relative_to(VAULT).parts[0] not in {".git", ".venv", ".trash"}
        )
        self.to_check = self.all_files

    def read(self, rel: str) -> bytes | None:
        try:
            return (VAULT / rel).read_bytes()
        except OSError:
            return None


class StagedTree:
    """Only staged files in their staged version; context = git index."""

    def __init__(self) -> None:
        self.all_files = sorted(self._git("ls-files", "-z").split("\0")[:-1])
        self.to_check = sorted(self._git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").split("\0")[:-1])

    @staticmethod
    def _git(*args: str, binary: bool = False):
        result = subprocess.run(["git", "-C", str(VAULT), "-c", "core.quotepath=off", *args],
                                capture_output=True, check=True)
        return result.stdout if binary else result.stdout.decode("utf-8")

    def read(self, rel: str) -> bytes | None:
        try:
            return self._git("show", f":{rel}", binary=True)
        except subprocess.CalledProcessError:
            return None


def is_hidden_or_skipped(rel: str) -> bool:
    parts = rel.split("/")
    return parts[0] in SKIP_TOP or any(p.startswith(".") for p in parts)


def is_exempt(rel: str) -> bool:
    return rel.rsplit("/", 1)[-1] in EXEMPT_NAMES or rel in EXEMPT_ROOT


def is_decision_path(rel: str) -> bool:
    """ADRs live in a decisions/ folder anywhere below 20_wiki/."""
    return rel.startswith("20_wiki/") and "/decisions/" in rel


def split_frontmatter(text: str):
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        return None
    lines = text.splitlines(keepends=True)
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n") == "---":
            return "".join(lines[1:i])
    return None


def normalize(value):
    """YAML dates -> ISO strings so JSON Schema can check them."""
    if isinstance(value, dict):
        return {str(k): normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize(v) for v in value]
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    return value


def strip_code(text: str) -> str:
    text = FENCE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    return INLINE_CODE.sub("", text)


def build_link_index(all_files: list[str]) -> set[str]:
    """Targets a wikilink may point to (like Obsidian: name or path, without .md)."""
    names: set[str] = set()
    for rel in all_files:
        for candidate in (rel.rsplit("/", 1)[-1], rel):
            names.add(candidate.lower())
            if candidate.endswith(".md"):
                names.add(candidate[:-3].lower())
    return names


class Validator:
    def __init__(self, config: dict, report: Report) -> None:
        self.config = config
        self.report = report
        self.levels = config["sensitivity_levels"]
        self.rank = {level: i for i, level in enumerate(self.levels)}
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        schema = copy.deepcopy(schema)
        schema["properties"]["sensitivity"] = {"enum": self.levels}
        schema["properties"]["owner"] = {"enum": config["owners"]}
        self.schema = jsonschema.Draft202012Validator(schema)

    def folder_sensitivity(self, rel: str) -> str:
        for prefix, level in self.config["folder_sensitivity"].items():
            if rel.startswith(prefix):
                return level
        return self.config["default_sensitivity"]

    def check_filename(self, rel: str) -> None:
        name = rel.rsplit("/", 1)[-1]
        if rel.startswith(self.config["log_dir"] + "/"):
            if not LOG_NAME.match(name):
                self.report.error("filename", rel, f"Log files are named YYYY-MM-DD.md, not '{name}'")
        elif is_decision_path(rel):
            if not ADR_NAME.match(name):
                self.report.error("filename", rel, f"ADRs are named adr-NNNN-title.md, not '{name}'")
        elif not KEBAB_MD.match(name):
            self.report.error("filename", rel, f"File name '{name}' is not kebab-case/ASCII")

    def check_note(self, rel: str, text: str, ids: dict[str, str], links: set[str]) -> None:
        self.report.files_checked += 1
        if not is_exempt(rel):
            self.check_filename(rel)
            self.check_frontmatter(rel, Path(rel).stem, text, ids)
        for lineno, line in enumerate(strip_code(text).splitlines(), start=1):
            for match in WIKILINK.finditer(line):
                target = match.group(1).strip()
                if not target:
                    continue  # [[#heading]] - link within the same note
                if target.lower().removesuffix(".md") not in links and target.lower() not in links:
                    self.report.error("broken-link", rel, f"Wikilink [[{target}]] points nowhere", line=lineno,
                                      private_message="Broken wikilink (details masked)")

    def check_frontmatter(self, rel: str, stem: str, text: str, ids: dict[str, str]) -> None:
        r = self.report
        fm_text = split_frontmatter(text)
        if fm_text is None:
            if not rel.startswith(tuple(self.config["frontmatter_optional"])):
                r.error("frontmatter-missing", rel, "No YAML frontmatter (--- … ---) at the start of the file")
            return
        try:
            data = yaml.safe_load(fm_text)
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            r.error("frontmatter-yaml", rel, f"YAML not parseable: {getattr(exc, 'problem', exc)}",
                    line=(mark.line + 2) if mark else None)
            return
        if not isinstance(data, dict):
            r.error("frontmatter-yaml", rel, "Frontmatter is not a YAML mapping")
            return
        data = normalize(data)

        for err in sorted(self.schema.iter_errors(data), key=lambda e: list(e.absolute_path)):
            field = ".".join(str(p) for p in err.absolute_path) or "(root)"
            r.error("schema", rel, f"{field}: {err.message}",
                    private_message=f"{field}: schema rule '{err.validator}' violated")

        note_id = data.get("id")
        if isinstance(note_id, str):
            if note_id != stem:
                r.error("id-mismatch", rel, f"id '{note_id}' ≠ file name '{stem}'")
            if note_id in ids and ids[note_id] != rel:
                r.error("id-duplicate", rel, f"id '{note_id}' already exists in {r.display(ids[note_id])}")
            else:
                ids[note_id] = rel

        sens = data.get("sensitivity")
        floor = self.folder_sensitivity(rel)
        if sens in self.rank and floor in self.rank and self.rank[sens] < self.rank[floor]:
            r.error("sensitivity", rel, f"sensitivity '{sens}' is looser than folder default '{floor}'")

        ntype = data.get("type")
        for prefix, expected in self.config["folder_types"].items():
            if rel.startswith(prefix) and ntype != expected:
                r.error("folder-type", rel, f"Notes in {prefix} need type: {expected} (is: {ntype!r})")
        if is_decision_path(rel) and ntype != "decision":
            r.error("folder-type", rel, f"Notes in decisions/ need type: decision (is: {ntype!r})")
        if rel.startswith("99_archive/") and data.get("status") != "deprecated":
            r.error("archive-status", rel, "Archived notes need status: deprecated")

        created, updated = data.get("created"), data.get("updated")
        if isinstance(created, str) and isinstance(updated, str) and updated < created:
            r.warn("dates", rel, f"updated ({updated}) is before created ({created})")

    def check_other_file(self, rel: str) -> None:
        name = rel.rsplit("/", 1)[-1]
        if name != ".DS_Store" and not KEBAB_ANY.match(name):
            self.report.warn("filename", rel, f"File name '{name}' is not kebab-case/ASCII")

    def check_secrets(self, rel: str, text: str) -> None:
        for lineno, line in enumerate(text.splitlines(), start=1):
            if SECRET_ALLOW in line:
                continue
            for code, pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    self.report.error("secret", rel, f"Possible secret ({code}) – content not shown",
                                      line=lineno, private_message=f"Possible secret ({code})")
                    break
            else:
                if IP_PORT.search(line):
                    self.report.warn("ip-port", rel, "IP address with port – only allowed if the service has no authentication",
                                     line=lineno, private_message="IP address with port")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validates frontmatter, file names, wikilinks, sensitivity and secrets in the knowledge vault.",
    )
    parser.add_argument("--json", action="store_true", help="Print the result as JSON")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--show-private", action="store_true",
                        help="Show paths/details from the restricted folder unmasked (local use only!)")
    parser.add_argument("--quiet", action="store_true", help="Print nothing on success")
    parser.add_argument("--staged", action="store_true",
                        help="Check only staged files in their staged version (for the pre-commit hook); "
                             "links and ids are checked against the git index")
    args = parser.parse_args()

    try:
        config = load_config()
        report = Report(show_private=args.show_private, restricted=config["restricted_folder"])
        validator = Validator(config, report)
    except (OSError, json.JSONDecodeError, jsonschema.SchemaError, KeyError) as exc:
        print(f"Configuration or schema not loadable: {exc}", file=sys.stderr)
        return 2
    try:
        tree = StagedTree() if args.staged else WorkingTree()
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"Git index not readable: {exc}", file=sys.stderr)
        return 2

    links = build_link_index(tree.all_files)
    checked = set(tree.to_check)
    # In staged mode the ids of the remaining indexed notes are fixed by their file
    # names (id = file name is checked whenever a note is committed).
    ids: dict[str, str] = {
        Path(rel).stem: rel for rel in tree.all_files
        if rel.endswith(".md") and rel not in checked and not is_hidden_or_skipped(rel) and not is_exempt(rel)
    }

    for rel in tree.to_check:
        is_note = not is_hidden_or_skipped(rel)
        scan_secrets = Path(rel).suffix.lower() in TEXT_EXT and not rel.startswith(SECRET_SKIP)
        if not (is_note or scan_secrets):
            continue
        data = tree.read(rel)
        if data is None:
            continue
        text = None
        if rel.endswith(".md") or scan_secrets:
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                if rel.endswith(".md"):
                    report.error("encoding", rel, "File is not UTF-8")
                continue
        if is_note:
            if rel.endswith(".md"):
                validator.check_note(rel, text, ids, links)
            else:
                validator.check_other_file(rel)
        if scan_secrets:
            validator.check_secrets(rel, text)

    failed = report.errors > 0 or (args.strict and report.warnings > 0)
    if args.json:
        print(json.dumps({"ok": not failed, "files_checked": report.files_checked, "errors": report.errors,
                          "warnings": report.warnings, "findings": report.findings}, ensure_ascii=False, indent=2))
    else:
        for f in report.findings:
            loc = f["path"] + (f":{f['line']}" if f["line"] else "")
            print(f"{f['level'].upper():7} {loc} [{f['code']}] {f['message']}")
        if not (args.quiet and not report.findings):
            status = "FAILED" if failed else "OK"
            print(f"\nvalidate: {status} – {report.files_checked} notes checked, "
                  f"{report.errors} errors, {report.warnings} warnings")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
