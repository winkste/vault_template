# vault_template

A reusable setup prompt for building a **knowledge vault** – a Markdown/Obsidian vault that serves as shared, durable memory for you and your AI agents (e.g. GitHub Copilot, Claude Code) in a dedicated project.

## Why

Chats with AI agents produce valuable knowledge – decisions, system details, solved problems, open tasks – that is lost when the session ends. A knowledge vault keeps it:

- **Durable and shared:** every agent and every human reads the same source of truth.
- **Open format:** plain Markdown with YAML frontmatter following the [Open Knowledge Format (OKF)](https://github.com/GoogleCloudPlatform/open-knowledge-format), versioned with git, readable without any special tool.
- **Controlled:** agents may read everything they are allowed to, but only *propose* changes; rules, permissions and confidential content stay under human control.

## What's in this repository

| File | Purpose |
|---|---|
| [`setup-prompt.md`](setup-prompt.md) | The prompt you give to your agent to build the vault |
| [`vault-kit/`](vault-kit/) | Ready-made building blocks to copy into the vault root: scripts, schema, note templates, git hook, `.gitignore`, starter task list |
| `README.md` | This description |
| `LICENSE` | MIT |

### Contents of `vault-kit/`

```
vault-kit/
├── .gitignore
├── 05_tasks/tasks.md                 # starter task list
└── _meta/
    ├── vault.config.json             # adapt: sensitivity levels, restricted folder, folder defaults, owners
    ├── schema/frontmatter.schema.json
    ├── templates/                    # entity, concept, howto, decision, source, policy, moc
    ├── hooks/pre-commit              # runs validate.py --staged
    └── scripts/
        ├── validate.py  changes.py  log.py  task.py
        ├── vaultlib.py               # shared config/helpers
        └── requirements.txt          # pyyaml, jsonschema
```

The scripts read their settings from `_meta/vault.config.json`, so they adapt to your parameters without code changes. They need Python 3.9+ and use `fcntl` for file locking (macOS/Linux; on Windows run them in WSL).

## How to use it

1. Copy [`setup-prompt.md`](setup-prompt.md).
2. Fill in the **Parameters** table at the top (purpose, path, language, agents, git remote, sensitivity levels, initial areas, compliance requirements).
3. Give the complete text to your agent – for GitHub Copilot, use agent mode with the target folder open in the workspace. Make `vault-kit/` available to the agent (e.g. clone this repository next to the new vault) so it copies the tested building blocks instead of writing them from scratch.
4. The agent first presents a plan and waits for your approval, then builds the vault step by step, asking one decision at a time with a recommendation.
5. Check the acceptance criteria at the end of the prompt.

> **Before using it at work:** clarify whether your company's policy allows AI tools to process the project's content, and keep the vault on an internal git remote – never a public one.

## The concept at a glance

**Folder structure**

```
00_inbox/     agents place proposals here – the human sorts them
05_tasks/     one central task list, grouped by area
10_raw/       immutable sources (exports, documents)
20_wiki/      curated knowledge: index, maps of content, notes, decisions (ADRs)
30_control/   rules and policies – written only by the human
40_log/       daily agent log
90_<level>/   most confidential content – off-limits for cloud-backed agents
99_archive/   nothing gets deleted, it gets archived
_meta/        conventions, schema, templates, scripts, git hook, agent integrations
```

**Core rules**

- One note = one concept, linked with `[[id]]`; every note has validated frontmatter (`id`, `type`, `status`, `sensitivity`, `owner`, provenance via `generated`/`verified`).
- Agents write only proposals into the inbox, log every change, add open work to the task list, and check existing decisions (ADRs) before proposing anything.
- Commits only on request; a pre-commit hook validates staged files.
- No secrets – ever.

**Tooling** (included in `vault-kit/`, Python standard library + `pyyaml` + `jsonschema`)

| Script | Job |
|---|---|
| `validate.py` | Checks frontmatter, file names, links, sensitivity and secret patterns; `--staged` mode for the git hook |
| `changes.py` | Detects new/changed sources in `10_raw/` via a hash manifest |
| `log.py` | Appends agent log entries safely (file locking) |
| `task.py` | Adds, completes and lists tasks safely (file locking) |

## Agent support

| Agent | Instruction file | Notes |
|---|---|---|
| GitHub Copilot | `.github/copilot-instructions.md`, `AGENTS.md` | Sees only the open workspace – add the vault to a multi-root workspace. No file-level permissions, so rules are advisory. |
| Claude Code | `CLAUDE.md` | Permission matrix can be enforced with `deny`/`allow` rules. |
| Other agents | `AGENTS.md` or equivalent | Point them to `_meta/CONVENTIONS.md`. |

## Origin

The approach was developed and tested in a private vault used by several agents (a coding agent and a multi-agent team), including concurrent writes, git hooks and an interview-based decision log. This template is the generalized, project-neutral version.

## License

[MIT](LICENSE)
