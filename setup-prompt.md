# Setup Prompt: Knowledge Vault as Shared Memory for Humans and AI Agents

> **How to use this template:** Fill in the "Parameters" section, delete lines that do not apply, and hand the entire text to your agent (e.g. GitHub Copilot in agent mode, Claude Code). Everything else is generic.

---

## Parameters (fill in before use)

| Parameter | Value |
|---|---|
| Purpose of the vault | `<e.g. project memory for project X – architecture, decisions, tasks>` |
| Vault path | `<absolute path, no spaces, not inside a cloud-sync folder>` |
| Content language | `<English / German / …>` (file names always `kebab-case`, ASCII) |
| Participating agents | `<e.g. github-copilot, claude-code>` – each with a short name used for `owner` and the log |
| Agent instruction files | `<e.g. .github/copilot-instructions.md, AGENTS.md, CLAUDE.md>` |
| Git remote | `<e.g. internal GitLab / GitHub Enterprise – never a public remote if content is confidential>` |
| Sensitivity levels | `<e.g. public < internal < confidential>` – highest level is off-limits for agents backed by a cloud LLM |
| Initial areas (subfolders of `20_wiki/`) | `<e.g. architecture, components, operations, team-knowledge>` |
| Compliance requirements | `<e.g. no customer data, no personnel data, AI tools approved by IT policy>` |

---

## Assignment

Set up an Obsidian-compatible vault that is at the same time:

1. **Shared memory** for the human and all participating agents – durable knowledge instead of lost chat histories.
2. **Open format** – Markdown with YAML frontmatter following the *Open Knowledge Format* (OKF, `GoogleCloudPlatform/open-knowledge-format`), version-controlled with git, tool-agnostic.
3. **Control bank** – rules and policies that agents read but never change.

## Working mode (binding for you as the agent)

- **Two phases:** First present a plan and wait for approval, then implement.
- **One decision per message:** Briefly list options as (a)/(b)/(c), then always give **"My recommendation: …, because …"**. Never ask many questions at once.
- **Do not invent anything:** Mark unknowns as open and ask. Cite sources.
- **Commit only on request**, push only after asking. No files outside the vault path without asking.
- **Before changing anything outside the vault** (configuration of other tools): create a backup and show the change.

## Step 0 – Align with OKF

Read the current OKF specification (`SPEC.md`). Adopt its required fields and field names, keep the additional fields below as extensions, and document the mapping in `_meta/okf-mapping.md`. If the spec is unreachable: say so and continue with the schema below.

Known deviations that stay intentionally: wikilinks `[[id]]` instead of Markdown links (for Obsidian); maps of content are named `moc-<area>.md`, and only `20_wiki/index.md` is the OKF root index document carrying `okf_version`.

## Folder structure

```
<vault>/
├── README.md                 # For humans: purpose, structure, workflow
├── AGENTS.md / CLAUDE.md / .github/copilot-instructions.md
│                             # Per agent: only a pointer to _meta/CONVENTIONS.md
├── _meta/
│   ├── CONVENTIONS.md        # Single source of truth for all rules
│   ├── okf-mapping.md
│   ├── schema/frontmatter.schema.json
│   ├── templates/            # One template per note type (also usable as Obsidian templates)
│   ├── scripts/              # validate.py, changes.py, log.py, task.py, requirements.txt
│   ├── hooks/pre-commit      # versioned, activated via core.hooksPath
│   ├── agents/               # Versioned agent integrations (skills, instructions)
│   └── state/                # e.g. hash manifest for 10_raw
├── 00_inbox/                 # Inbox; agents place proposals here
├── 05_tasks/tasks.md         # Central task list, grouped by area
├── 10_raw/                   # Sources (exports, documents) – immutable, agents read only
├── 20_wiki/                  # Curated knowledge
│   ├── index.md              # Central map of content (OKF root)
│   └── <area>/               # per area: moc-<area>.md, notes, decisions/ (ADRs)
├── 30_control/               # Rules / policies – ONLY the human writes here
├── 40_log/                   # Agent log, one file per day (YYYY-MM-DD.md)
├── 90_<highest-level>/       # e.g. 90_confidential – off-limits for cloud agents
└── 99_archive/               # Move here instead of deleting
```

Do not create empty areas in advance – new areas appear as subfolders when their first content arrives.

## Frontmatter schema

```yaml
---
id: kebab-case-id            # = file name without .md, unique within the vault
title: "Title"               # quote values that contain a colon
description: "One sentence."
type: concept                # entity | concept | howto | decision | source | policy | log | moc | tasklist
status: draft                # draft | stable | deprecated   (OKF)
sensitivity: internal        # per parameter; never looser than the folder default
owner: <agent-short-name>    # human | <agent short names> – governs write permissions
tags: [area]
sources:                     # OKF: list of objects
  - resource: "[[source-id]]"   # or URL / repository path
generated:                   # OKF: provenance
  by: <agent>/<model>        # or human:<id>, process:<name>
  at: 2026-01-01T10:00:00+01:00
verified:                    # optional: confirmation by the human
  - by: human:<id>
    at: 2026-01-01T12:00:00+01:00
created: 2026-01-01
updated: 2026-01-01
---
```

Additional fields per type: decisions (`type: decision`, in `decisions/`, file name `adr-NNNN-title.md`, number sequential across the whole vault) require `decision_status` (proposed | accepted | superseded) and optionally `supersedes`.

## Contents of CONVENTIONS.md (at least)

1. Purpose and meaning of each folder, including its default sensitivity.
2. **Permission matrix** folder × actor (human / each agent):
   - `10_raw/`, `30_control/`, `_meta/`: agents read only.
   - `00_inbox/`: agents create new files, **never overwrite**.
   - `20_wiki/`: agents only change notes with `owner` ≠ `human`; for human notes they place a proposal in `00_inbox/`.
   - `05_tasks/`, `40_log/`: agents only via the scripts (file locking).
   - Highest sensitivity level: off-limits for agents backed by a cloud LLM. **Before the first content is stored there, implement hard protection** (separate OS user or encryption) – rules alone are not enough.
3. One note = one concept; link with `[[id]]`; every new note is linked in the map of content of its area.
4. **Check the area's ADRs before every proposal** – no contradiction to accepted decisions, or state it explicitly.
5. Never delete → move to `99_archive/`, set `status: deprecated`.
6. Every agent change: log entry via `log.py`; **commits only on request**, then with prefix `[<agent>]`.
7. Tasks: central list via `task.py`; agents add open work and only check off what they completed themselves; no confidential tasks in the general list.
8. **No secrets** (tokens, passwords, keys, internal credentials) – not even in the highest sensitivity level.
9. `validate.py` before every commit (pre-commit hook).

## Technical implementation

- `git init`, `.gitignore`: `.obsidian/workspace*.json`, `.trash/`, `.DS_Store`, `.venv/`, `__pycache__/`, local agent settings. Otherwise version `.obsidian/`; keep Obsidian Sync off if content is confidential.
- Python 3, a dedicated `.venv` inside the vault, standard library + `pyyaml` + `jsonschema` only. Every script supports `--help` and `--json` and exits non-zero on errors.
- **`validate.py`:** frontmatter against the schema; `id` = file name and unique; file names; sensitivity never looser than the folder default; folder-specific required fields; broken wikilinks (ignoring code blocks); secret patterns (with human approval via the comment `validate:allow-secret`). Output masks paths and details from the most confidential folder. Option **`--staged`**: check only staged files in their staged version, links/ids against the git index – so unfinished notes never block unrelated commits.
- **pre-commit hook** in `_meta/hooks/`, activated with `git config core.hooksPath _meta/hooks`, runs `validate.py --staged`.
- **`changes.py`:** SHA-256 manifest of `10_raw/` in `_meta/state/`, reports new/changed/deleted files; `--update` after processing. No LLM call.
- **`log.py`:** appends entries with file locking (`fcntl.flock`) to `40_log/<date>.md` and creates the daily file with valid frontmatter. Format: `## HH:MM [actor] Title` + `- Changed: [[ids]]` + `- Reason: …`.
- **`task.py`:** `add` / `done` / `list` for `05_tasks/tasks.md`, with file locking. Line format compatible with the Obsidian "Tasks" plugin: `- [ ] Text – [[note-id]] 📅 due ➕ created (who)`; completed items move with `✅ date` to `## Done`.
- Obsidian: Templates plugin pointing to `_meta/templates/`, new files and attachments go to `00_inbox/`.

## Agent integration

- Each instruction file contains **only** a pointer to `_meta/CONVENTIONS.md` plus the essentials: read via `20_wiki/index.md`, write only as a proposal in `00_inbox/`, log via `log.py`, tasks via `task.py`, check ADRs, do not commit.
- **GitHub Copilot:** instructions in `.github/copilot-instructions.md` (and/or `AGENTS.md`). Copilot only sees the open workspace – add the vault as a folder to a multi-root workspace or open it within the project workspace. Copilot has no fine-grained file permissions: the permission matrix only works as a rule there, so protect confidential content technically or keep it out of the workspace.
- **Agents with a permission system** (e.g. Claude Code): additionally express the permission matrix as `deny`/`allow` rules.
- **Agents with their own memory:** the vault is the source of durable knowledge; the agent's memory stays working memory with a pointer to the vault.
- Versioned agent building blocks (skills, instructions) live in `_meta/agents/` and are included read-only.

## Good practices and pitfalls

- Never write Markdown files through unquoted shell heredocs – backticks get executed as commands. Use a file-writing tool or `<<'EOF'`.
- Quote YAML frontmatter values that contain `:`.
- Tools with multiple profiles often have **separate** configuration and `.env` files per profile – check each one.
- Integrate external knowledge (e.g. reports from other chats) as `status: draft` first, collect contradictions with the verified state in a table, and have the human confirm (`verified`).
- The human places source files in `10_raw/`; notes link them via `[[file-name.ext]]`.

## Initial content (after the structure setup, confirm separately)

1. `20_wiki/index.md` and one map of content per area.
2. One note per existing repository/system describing purpose, structure and conventions – **do not duplicate the repository's content**, link to it instead (with commit reference).
3. Decisions already made as ADRs – **ask for them in an interview, do not invent them**; rationale only from the human.
4. Fill the task list with the open points from the setup.

## Acceptance criteria

- `validate.py` runs without errors across the entire vault.
- A deliberately broken, staged test note is rejected by the pre-commit hook; an unfinished, unstaged note does not block an unrelated commit.
- `changes.py` detects a new file in `10_raw/`.
- `log.py` and `task.py` lose no entry under 20 concurrent invocations.
- The vault opens in Obsidian; the graph shows `index.md` at the center.
- Every participating agent finds the rules via its instruction file, reads via `index.md`, and creates a valid proposal in `00_inbox/`.
- Wrap-up: a short summary of what was created and open questions for the human.
