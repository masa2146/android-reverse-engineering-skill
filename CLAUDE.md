# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A Claude Code **plugin marketplace** (a fork of `SimoneAvogadro/android-reverse-engineering-skill`) hosting three plugins:

- `plugins/android-reverse-engineering/` — **upstream, vendored. Never modify.** Decompiles APK/XAPK/JAR/AAR with jadx, extracts HTTP APIs, recovers R8-obfuscated Kotlin names.
- `plugins/clone-app/` — **this project's work.** A `/clone-app` skill that takes a Google Play URL, drives the RE plugin to reverse engineer the app, scrapes store metrics, estimates AI-assisted clone effort + infra cost, writes a viability report, and optionally hands off to the `writing-plans` skill.
- `plugins/market-research/` — **this project's work.** A `/market-research` skill that autonomously scans the app/game market (free web + LLM trend synthesis), scores ≥10 non-repeating clone candidates (cloneability + market opportunity + monetization fit), and hands user-picked candidates to `clone-app`.

These two project plugins are the first stages of a planned three-stage **discover → analyze → build** pipeline (chained skill handoffs, no central orchestrator): `market-research` → `clone-app` → a future `hermes-build` plugin (autonomous build → test → Firebase → ads → Play internal-testing track via [hermes-agent](https://github.com/nousresearch/hermes-agent)). The umbrella design lives in `docs/superpowers/specs/2026-06-22-market-to-build-pipeline-design.md`; `hermes-build` and the `clone-app` Phase 7 "Build with hermes" branch are **not yet implemented**.

There is no compiled artifact and no application runtime. "The code" is bash + Python helper scripts plus Markdown skill/command/reference docs that Claude Code loads at session time.

## The hard constraint

`plugins/android-reverse-engineering/` is the upstream tree. Keeping it byte-identical is what makes `git pull upstream master` conflict-free. Before committing, this must print nothing:

```bash
git status --porcelain plugins/android-reverse-engineering/
```

Two remotes: `origin` = `masa2146/clone-app-skill` (this fork), `upstream` = `SimoneAvogadro/android-reverse-engineering-skill`. Sync upstream with `git pull upstream master`. The only shared file the project plugins touch is root `.claude-plugin/marketplace.json` (it now lists three plugins: the upstream RE entry stays attributed to Simone Avogadro and byte-identical; `clone-app` and `market-research` are appended) and—if ever—root `README.md`; everything else lives under each plugin's own dir.

## Commands

```bash
# Full clone-app test suite (5 suites, ~28 assertions). Run from repo root.
bash plugins/clone-app/tests/run-all.sh

# A single test
bash    plugins/clone-app/tests/test-extract-package.sh
python3 plugins/clone-app/tests/test-scrape-play-store.py

# Structural smoke test: files present, scripts executable, JSON valid, all plugins in marketplace
bash plugins/clone-app/tests/smoke-structure.sh

# Full market-research suite (3 suites: structure + bash + python). Run from repo root.
bash plugins/market-research/tests/run-all.sh

# A single market-research test
python3 plugins/market-research/tests/test-fetch-charts.py
python3 plugins/market-research/tests/test-history.py
bash    plugins/market-research/tests/test-skill-content.sh

# Validate the JSON manifests
python3 -c "import json; json.load(open('.claude-plugin/marketplace.json')); json.load(open('plugins/clone-app/.claude-plugin/plugin.json')); json.load(open('plugins/market-research/.claude-plugin/plugin.json'))"
```

Shell is zsh but every script uses `#!/usr/bin/env bash` — invoke with `bash <path>`, not `sh`. `shopt` etc. fail under zsh; wrap in `bash -c '...'`. Python is stdlib-only (`urllib`, `json`, `re`); no pip, no virtualenv.

**bash 4+ is required at runtime.** The upstream RE scripts (`fingerprint.sh`, `find-api-calls.sh`) use `${VAR,,}` and break with "bad substitution" on macOS's stock bash 3.2. You cannot patch them (upstream-untouched rule), so the fix is `brew install bash`; `#!/usr/bin/env bash` then resolves to the modern one. `resolve-re-scripts.sh` emits a stderr WARNING when it detects bash < 4.

**APK source is APKCombo, not APKPure.** The old `d.apkpure.com/b/APK/<pkg>` endpoint now returns an HTTP 403 Cloudflare challenge for every package. `download-apk.sh` instead GETs `apkcombo.com/app/<pkg>/download/apk` with a browser User-Agent, greps the embedded `/r2?u=<signed-url>` link out of the HTML, and downloads that (no JavaScript needed; the URL slug segment is ignored by the server so a literal `app` works for any package).

## How clone-app is wired

`plugins/clone-app/skills/clone-app/SKILL.md` is the orchestrator — an 8-phase (0–7) prose workflow Claude executes. Phases split into two kinds:

- **Deterministic steps → helper scripts** under `skills/clone-app/scripts/`, each independently testable: `extract-package.sh` (Play URL → package), `download-apk.sh` (APKCombo two-step download, 3 retries, apk-vs-xapk by ZIP contents), `resolve-re-scripts.sh` (locates the sibling RE plugin's `scripts/` dir + warns if `bash` is < 4), `scrape-play-store.py` (Play page → metrics JSON via embedded ld+json), `check-appstore.py` (iTunes Search → iOS presence).
- **AI-judgment steps → reference rubrics** under `skills/clone-app/references/` (`stack-recommendation-guide`, `effort-estimation-guide`, `infra-cost-guide`, `report-template`). These keep effort/cost/verdict output consistent; edit the rubric, not the prose, to change how estimates are produced.

clone-app never hardcodes RE script paths. It calls `resolve-re-scripts.sh`, which from `plugins/clone-app/` walks to `plugins/android-reverse-engineering/skills/android-reverse-engineering/scripts/` (honoring `$CLAUDE_PLUGIN_ROOT`, falling back to deriving its own location). Phase 2 then invokes that dir's `fingerprint.sh`, `check-deps.sh`, `decompile.sh -o "$WORK/output"`, `recover-kotlin-names.sh`, `find-api-calls.sh`.

Two runtime conventions the scripts and SKILL.md share:
- **Working dir** is `./work/{package}/` relative to the user's cwd (never inside the plugin), created by `init-workdir.sh` with three layers: `deliverables/` (reports, build spec, reconstruction — written for a person), `extracted/` (clean data: game assets, API surface, RE digests, `store/`), `raw/` (package, decompiled sources, unpack scratch — regenerable). Decompile output must land at `$WORK/raw/decompiled/` via `decompile.sh -o` — `decompile.sh` otherwise defaults to a relative `<basename>-decompiled` dir in cwd. Nothing in `raw/` is deleted automatically; `clean-workdir.sh` is the user's call. `migrate-workdir.sh` converts a pre-layout flat working dir.
- **Effort is measured in "AI Sprints"** (one focused Claude session, ~2–4h review), never calendar time.

SKILL.md pauses for the user at exactly two points: Phase 4 (choose clone stack) and Phase 7 (proceed to implementation plan?). Phase 7's "yes" path invokes `superpowers:writing-plans`.

## How market-research is wired

`plugins/market-research/skills/market-research/SKILL.md` is a 6-phase (0–5) prose orchestrator following the same **scripts-for-deterministic / rubrics-for-judgment** split as clone-app:

- **Scripts** under `skills/market-research/scripts/`: `fetch-charts.py` (Apple App Store RSS chart feeds → normalized JSON; `<feed>` ∈ `topfreeapplications`/`toppaidapplications`/`topgrossingapplications`, flags `--region`/`--limit`/`--json-file`) and `history.py` (the non-repeat memory; subcommands `filter`/`add` read a candidates JSON array on **stdin**, flag `--history`; `cand_key` = package if present, else lowercased/stripped name).
- **Rubrics** under `skills/market-research/references/`: `research-angles.md` (rotating category × region × niche seeds for run-to-run variety), `scoring-guide.md` (the 0–100 weighted composite: cloneability 35 + market 35 + monetization 20 + niche 10), `report-template.md`.

Working dir is `./work/market-research/` (relative to cwd, never inside the plugin), holding `history.json` (every past suggestion — the cross-run non-repeat memory) and `research-<date>.md`. Variety comes from seed rotation **plus** history exclusion. `history.py add` is deterministic — it takes `--date`/`--run-id` rather than reading a clock — so tests need no fixture clock. Phase 5 resolves each user-picked candidate to a Play package/URL (it may only have an iOS bundle id or a bare name) **before** invoking `clone-app`.

## Test pattern

Bash tests use `set -uo pipefail` (intentionally not `-e`) and aggregate failures into a `fail` var so every assertion runs; the script exits non-zero if any failed. Python scrapers are tested offline against `tests/fixtures/` via `--html-file` / `--json-file` flags — never hitting the network. New scrape logic needs a fixture, not a live call.

## Conventions

- Plugin/skill identity is layered: `marketplace.json` top-level `name` (`clone-app-skill`) is what `/plugin install <plugin>@clone-app-skill` resolves against; each plugin's `.claude-plugin/plugin.json` carries its own `name`. The upstream plugin entry inside `marketplace.json` stays attributed to Simone Avogadro.
- Commits follow Conventional Commits scoped to the plugin: `feat(clone-app): …`, `test(market-research): …`, `chore(market-research): …`.
- `docs/superpowers/specs/` and `docs/superpowers/plans/` hold the design specs and task-by-task implementation plans the project plugins were built from — read them for the rationale behind a phase or script. `.superpowers/sdd/` is git-ignored scratch (subagent-driven-development progress ledger + per-task briefs/reports); not part of the deliverable.
- Each project plugin mirrors the same layout — `skills/<name>/{SKILL.md,scripts/,references/}`, `commands/<name>.md`, `tests/{run-all.sh,smoke-structure.sh,test-*}`, `tests/fixtures/`, `.claude-plugin/plugin.json`, `README.md` — so a new plugin starts by copying that shape.
