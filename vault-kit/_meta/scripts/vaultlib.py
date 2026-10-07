"""Shared helpers for the vault scripts: vault root, configuration, actor format."""

from __future__ import annotations

import json
import re
from pathlib import Path

VAULT = Path(__file__).resolve().parents[2]
CONFIG_PATH = VAULT / "_meta" / "vault.config.json"

ACTOR = re.compile(r"^(human(:[a-z0-9._-]+)?|process:[a-z0-9._-]+|[a-z0-9._-]+(/[A-Za-z0-9._-]+)?)$")
NOTE_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

DEFAULTS = {
    "sensitivity_levels": ["public", "internal", "confidential"],
    "default_sensitivity": "internal",
    "folder_sensitivity": {},
    "restricted_folder": "90_confidential/",
    "owners": ["human"],
    "frontmatter_optional": ["10_raw/"],
    "raw_dir": "10_raw",
    "log_dir": "40_log",
    "tasks_file": "05_tasks/tasks.md",
    "folder_types": {},
}


def load_config() -> dict:
    """Configuration from _meta/vault.config.json, missing keys filled with defaults."""
    config = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        config.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    return config


def owner_of(actor: str, owners: list[str]) -> str:
    """Map an actor such as 'claude-code/model' or 'human:jane' to an owner value."""
    base = actor.split("/", 1)[0].split(":", 1)[0]
    if base in owners:
        return base
    return next((o for o in owners if o != "human"), "human")
