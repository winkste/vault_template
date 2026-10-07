# Setup-Prompt: Knowledge Vault als gemeinsames Gedächtnis für Mensch und KI-Agents

> **So verwendest du diese Vorlage:** Fülle den Abschnitt „Parameter“ aus, lösche nicht zutreffende Zeilen und gib den gesamten Text deinem Agent (z. B. GitHub Copilot im Agent-Modus, Claude Code). Alles andere ist allgemeingültig.

---

## Parameter (vor dem Einsatz ausfüllen)

| Parameter | Wert |
|---|---|
| Zweck des Vaults | `<z. B. Projektgedächtnis für Projekt X – Architektur, Entscheidungen, Aufgaben>` |
| Vault-Pfad | `<absoluter Pfad, ohne Leerzeichen, nicht in einem Cloud-Sync-Ordner>` |
| Sprache der Inhalte | `<Deutsch / Englisch>` (Dateinamen immer `kebab-case`, ASCII) |
| Beteiligte Agents | `<z. B. github-copilot, claude-code>` – je mit Kurzname für `owner` und Log |
| Agent-Anweisungsdateien | `<z. B. .github/copilot-instructions.md, AGENTS.md, CLAUDE.md>` |
| Git-Remote | `<z. B. internes GitLab/GitHub Enterprise – nie ein öffentliches Remote, falls vertrauliche Inhalte>` |
| Vertraulichkeitsstufen | `<z. B. public < internal < confidential>` – höchste Stufe für Agents mit Cloud-LLM tabu |
| Erste Bereiche (Unterordner von `20_wiki/`) | `<z. B. architektur, komponenten, betrieb, team-wissen>` |
| Compliance-Vorgaben | `<z. B. keine Kundendaten, keine Personaldaten, Freigabe für KI-Tools>` |

---

## Auftrag

Richte einen Obsidian-kompatiblen Vault ein, der gleichzeitig ist:

1. **Gemeinsames Gedächtnis** für den Menschen und alle beteiligten Agents – dauerhaftes Wissen statt verlorener Chat-Verläufe.
2. **Offenes Format** – Markdown mit YAML-Frontmatter nach dem *Open Knowledge Format* (OKF, `GoogleCloudPlatform/open-knowledge-format`), git-versioniert, werkzeugunabhängig.
3. **Kontrollbank** – Regeln und Vorgaben, die Agents lesen, aber nicht ändern.

## Arbeitsweise (verbindlich für dich als Agent)

- **Zwei Phasen:** Erst einen Plan vorlegen und auf Freigabe warten, dann umsetzen.
- **Eine Entscheidung pro Nachricht:** Optionen kurz als (a)/(b)/(c), dann immer **„Meine Empfehlung: …, weil …“**. Nicht viele Fragen auf einmal.
- **Nichts erfinden:** Unbekanntes als offen markieren und nachfragen. Quellen nennen.
- **Commits nur auf Anfrage**, Push nur nach Rückfrage. Keine Dateien außerhalb des Vault-Pfads ohne Rückfrage.
- **Vor Änderungen außerhalb des Vaults** (Konfigurationen anderer Werkzeuge): Backup anlegen, Änderung zeigen.

## Schritt 0 – OKF abgleichen

Lies die aktuelle OKF-Spezifikation (`SPEC.md`). Übernimm Pflichtfelder und Feldnamen, behalte die Zusatzfelder unten als Erweiterung und dokumentiere das Mapping in `_meta/okf-mapping.md`. Ist die Spec nicht erreichbar: sag es und arbeite mit dem Schema unten.

Bekannte Abweichungen, die bewusst so bleiben: Wikilinks `[[id]]` statt Markdown-Links (für Obsidian); MOCs heißen `moc-<bereich>.md`, nur `20_wiki/index.md` ist das OKF-Root-Index-Dokument mit `okf_version`.

## Ordnerstruktur

```
<vault>/
├── README.md                 # Für Menschen: Zweck, Struktur, Workflow
├── AGENTS.md / CLAUDE.md / .github/copilot-instructions.md
│                             # Je Agent: nur ein Verweis auf _meta/CONVENTIONS.md
├── _meta/
│   ├── CONVENTIONS.md        # Single Source of Truth für alle Regeln
│   ├── okf-mapping.md
│   ├── schema/frontmatter.schema.json
│   ├── templates/            # Ein Template pro Notiztyp (auch als Obsidian-Templates)
│   ├── scripts/              # validate.py, changes.py, log.py, aufgabe.py, requirements.txt
│   ├── hooks/pre-commit      # versioniert, aktiviert per core.hooksPath
│   ├── agents/               # Versionierte Agent-Anbindungen (Skills, Instruktionen)
│   └── state/                # z. B. Hash-Manifest für 10_raw
├── 00_inbox/                 # Eingang; Agents legen hier Vorschläge ab
├── 05_aufgaben/aufgaben.md   # Zentrale Aufgabenliste nach Bereichen
├── 10_raw/                   # Quellen (Exporte, Dokumente) – unveränderlich, Agents lesen nur
├── 20_wiki/                  # Kuratiertes Wissen
│   ├── index.md              # Zentrale Map of Content (OKF-Root)
│   └── <bereich>/            # je Bereich: moc-<bereich>.md, Notes, decisions/ (ADRs)
├── 30_control/               # Vorgaben/Policies – NUR der Mensch schreibt
├── 40_log/                   # Agent-Protokoll, eine Datei pro Tag (JJJJ-MM-TT.md)
├── 90_<höchste-stufe>/       # z. B. 90_confidential – für Cloud-Agents tabu
└── 99_archive/               # Statt Löschen hierher verschieben
```

Leere Bereiche nicht auf Vorrat anlegen – neue Bereiche entstehen als Unterordner, wenn der erste Inhalt kommt.

## Frontmatter-Schema

```yaml
---
id: kebab-case-id            # = Dateiname ohne .md, im Vault eindeutig
title: "Titel"               # Werte mit Doppelpunkt in Anführungszeichen
description: "Ein Satz."
type: concept                # entity | concept | howto | decision | source | policy | log | moc | tasklist
status: draft                # draft | stable | deprecated   (OKF)
sensitivity: internal        # gemäß Parameter; nie lockerer als der Ordner-Default
owner: <agent-kurzname>      # human | <agent-kurznamen> – regelt Schreibrechte
tags: [bereich]
sources:                     # OKF: Liste von Objekten
  - resource: "[[quelle-id]]"   # oder URL / Repo-Pfad
generated:                   # OKF: Herkunft
  by: <agent>/<modell>       # oder human:<id>, process:<name>
  at: 2026-01-01T10:00:00+01:00
verified:                    # optional: Bestätigung durch den Menschen
  - by: human:<id>
    at: 2026-01-01T12:00:00+01:00
created: 2026-01-01
updated: 2026-01-01
---
```

Zusatzfelder je Typ: Entscheidungen (`type: decision`, in `decisions/`, Dateiname `adr-NNNN-titel.md`, Nummer vault-weit fortlaufend) brauchen `decision_status` (proposed | accepted | superseded) und optional `supersedes`.

## Inhalte von CONVENTIONS.md (mindestens)

1. Zweck und Ordnerbedeutung mit Default-Vertraulichkeit je Ordner.
2. **Rechte-Matrix** Ordner × Akteur (Mensch / je Agent):
   - `10_raw/`, `30_control/`, `_meta/`: Agents nur lesen.
   - `00_inbox/`: Agents legen neue Dateien an, **nie überschreiben**.
   - `20_wiki/`: Agents ändern nur Notes mit `owner` ≠ `human`; für Human-Notes Vorschlag in `00_inbox/`.
   - `05_aufgaben/`, `40_log/`: Agents nur über die Scripts (Dateisperre).
   - Höchste Vertraulichkeitsstufe: für Agents mit Cloud-LLM tabu. **Bevor dort der erste Inhalt entsteht, wird ein harter Schutz umgesetzt** (eigener Benutzer oder Verschlüsselung) – Regeln allein reichen nicht.
3. Eine Note = ein Konzept; Verlinkung per `[[id]]`; jede neue Note in der MOC ihres Bereichs.
4. **Vor jedem Vorschlag die ADRs des Bereichs prüfen** – kein Widerspruch zu akzeptierten Entscheidungen, oder ihn ausdrücklich nennen.
5. Nichts löschen → `99_archive/`, `status: deprecated`.
6. Jede Agent-Änderung: Log-Eintrag über `log.py`; **Commits nur auf Anfrage**, dann mit Präfix `[<agent>]`.
7. Aufgaben: zentrale Liste über `aufgabe.py`; Agents tragen offene Arbeit ein, haken nur selbst Erledigtes ab; keine vertraulichen Aufgaben in der allgemeinen Liste.
8. **Keine Secrets** (Tokens, Passwörter, Keys, interne Zugangsdaten) – auch nicht in der höchsten Stufe.
9. `validate.py` vor jedem Commit (pre-commit-Hook).

## Technische Umsetzung

- `git init`, `.gitignore`: `.obsidian/workspace*.json`, `.trash/`, `.DS_Store`, `.venv/`, `__pycache__/`, lokale Agent-Einstellungen. `.obsidian/` sonst versionieren; Obsidian Sync aus, falls vertrauliche Inhalte.
- Python 3, eigenes `.venv` im Vault, nur Standardbibliothek + `pyyaml` + `jsonschema`. Alle Scripts mit `--help`, `--json`, Exit-Code ≠ 0 bei Fehlern.
- **`validate.py`:** Frontmatter gegen Schema; `id` = Dateiname und eindeutig; Dateinamen; Vertraulichkeit nie lockerer als Ordner-Default; ordnerspezifische Pflichtfelder; kaputte Wikilinks (Code-Blöcke ignorieren); Secret-Muster (mit menschlicher Freigabe per Kommentar `validate:allow-secret`). Ausgabe maskiert Pfade und Details aus dem vertraulichsten Ordner. Option **`--staged`**: nur gestagte Dateien in gestagter Fassung prüfen, Links/ids gegen den Git-Index – damit unfertige Notes keine anderen Commits blockieren.
- **pre-commit-Hook** in `_meta/hooks/`, aktiviert mit `git config core.hooksPath _meta/hooks`, ruft `validate.py --staged`.
- **`changes.py`:** SHA-256-Manifest von `10_raw/` in `_meta/state/`, meldet neu/geändert/gelöscht; `--update` nach der Verarbeitung. Kein LLM-Aufruf.
- **`log.py`:** hängt Einträge mit Dateisperre (`fcntl.flock`) an `40_log/<datum>.md` an, legt die Tagesdatei mit gültigem Frontmatter an. Format: `## HH:MM [akteur] Titel` + `- Geändert: [[ids]]` + `- Grund: …`.
- **`aufgabe.py`:** `add` / `done` / `list` für `05_aufgaben/aufgaben.md`, mit Dateisperre. Zeilenformat kompatibel zum Obsidian-Plugin „Tasks“: `- [ ] Text – [[note-id]] 📅 fällig ➕ angelegt (wer)`; Erledigtes wandert mit `✅ Datum` in `## Erledigt`.
- Obsidian: Templates-Plugin auf `_meta/templates/`, neue Dateien und Anhänge nach `00_inbox/`.

## Anbindung der Agents

- Jede Anweisungsdatei enthält **nur** einen Verweis auf `_meta/CONVENTIONS.md` plus den Kern: lesen über `20_wiki/index.md`, schreiben nur als Vorschlag in `00_inbox/`, Log über `log.py`, Aufgaben über `aufgabe.py`, ADRs prüfen, nicht committen.
- **GitHub Copilot:** Anweisungen in `.github/copilot-instructions.md` (bzw. `AGENTS.md`). Copilot sieht nur den geöffneten Workspace – den Vault daher als Ordner in einen Multi-Root-Workspace aufnehmen oder im Projekt-Workspace öffnen. Copilot hat keine feingranularen Datei-Sperren: Die Rechte-Matrix wirkt dort nur als Regel; vertrauliche Inhalte daher technisch schützen oder nicht in den Workspace aufnehmen.
- **Agents mit Rechte-System** (z. B. Claude Code): Rechte-Matrix zusätzlich als `deny`/`allow`-Regeln abbilden.
- **Agents mit eigenen Memories:** Vault ist die Quelle für dauerhaftes Wissen; das Agent-Memory bleibt Arbeitsgedächtnis mit Verweis auf den Vault.
- Versionierte Agent-Bausteine (Skills, Instruktionen) liegen in `_meta/agents/` und werden schreibgeschützt eingebunden.

## Bewährte Praxis und Fallstricke

- Markdown-Dateien nie über ungequotete Shell-Heredocs schreiben – Backticks werden sonst als Befehle ausgeführt. Datei-Werkzeug oder `<<'EOF'` verwenden.
- Werte mit `:` im YAML-Frontmatter in Anführungszeichen setzen.
- Bei Werkzeugen mit mehreren Profilen haben Profile oft **eigene** Konfigurations- und `.env`-Dateien – jede einzeln prüfen.
- Übernommenes Fremdwissen (z. B. Berichte aus anderen Chats) zuerst als `status: draft` einarbeiten, Widersprüche zum geprüften Stand in einer Tabelle sammeln und vom Menschen bestätigen lassen (`verified`).
- Quellen-Dateien in `10_raw/` legt der Mensch ab; Notes verlinken sie per `[[dateiname.ext]]`.

## Erstbefüllung (nach Struktur-Setup, separat bestätigen lassen)

1. `20_wiki/index.md` und je eine MOC pro Bereich.
2. Pro bestehendem Repo/System eine Note mit Zweck, Aufbau und Konventionen – **nicht den Inhalt des Repos duplizieren**, sondern darauf verweisen (mit Commit-Stand).
3. Bereits getroffene Entscheidungen als ADRs – **im Interview erfragen, nicht erfinden**; Gründe nur vom Menschen.
4. Aufgabenliste mit den offenen Punkten aus dem Setup befüllen.

## Abnahmekriterien

- `validate.py` läuft fehlerfrei über den gesamten Vault.
- Eine absichtlich kaputte, gestagte Test-Note wird vom pre-commit-Hook abgelehnt; eine unfertige, nicht gestagte Note blockiert keinen anderen Commit.
- `changes.py` erkennt eine neue Datei in `10_raw/`.
- `log.py` und `aufgabe.py` verlieren bei 20 gleichzeitigen Aufrufen keinen Eintrag.
- Der Vault lässt sich in Obsidian öffnen; der Graph zeigt `index.md` als Zentrum.
- Jeder beteiligte Agent findet über seine Anweisungsdatei die Regeln, liest über `index.md` und legt einen gültigen Vorschlag in `00_inbox/` an.
- Abschluss: kurze Zusammenfassung, was angelegt wurde, und offene Fragen an den Menschen.
