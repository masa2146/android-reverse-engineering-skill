# clone-app — Clone Feasibility Analyzer (Claude Code skill)

Give it a Google Play URL. It downloads the APK, reverse engineers the tech
stack and APIs (via the sibling `android-reverse-engineering` plugin), analyzes
the app's store presence, estimates **AI-assisted** build effort (in AI Sprints)
and monthly infrastructure cost, judges market viability (GO / CONDITIONAL GO /
NO GO), and — if you approve — generates a full implementation plan.

## Requirements
- The `android-reverse-engineering` plugin (ships in this same repo).
- Java JDK 17+ and jadx (the RE plugin auto-installs jadx if missing).
- `curl`, Python 3 (stdlib only), `unzip`.
- **bash 4+**. macOS ships bash 3.2, but the RE scripts use bash-4 syntax
  (`${VAR,,}`) and fail with "bad substitution" on 3.2. Install a modern bash
  with `brew install bash` — `#!/usr/bin/env bash` then picks it up.

## APK source
APKs/XAPKs are fetched from **APKCombo**. The previous APKPure direct endpoint
(`d.apkpure.com/b/APK/<pkg>`) now returns an HTTP 403 Cloudflare bot challenge
for every package, so it is no longer usable from a plain `curl`. If an app is
not on APKCombo, pass a local `.apk`/`.xapk` path instead.

## Install
```text
/plugin marketplace add https://github.com/masa2146/clone-app-skill
/plugin install android-reverse-engineering@clone-app-skill
/plugin install clone-app@clone-app-skill
```

## Usage
```text
/clone-app https://play.google.com/store/apps/details?id=com.example.app
```
Or natural language: "Analyze this Play Store app for cloning: <url>".

The skill pauses twice for your input: choosing the clone stack, and deciding
whether to generate the implementation plan.

## Output
```
./work/<package>/
├── app.apk | app.xapk
├── output/            # decompiled sources + Kotlin name maps
├── play.json          # store metrics
├── appstore.json      # iOS presence
└── clone-report-YYYY-MM-DD.md
```

## Keeping the RE plugin up to date
This repo is a fork. To pull upstream improvements:
```bash
git remote add upstream https://github.com/SimoneAvogadro/android-reverse-engineering-skill.git
git pull upstream master
```
The clone-app plugin lives in its own directory, so upstream updates to
`android-reverse-engineering` merge cleanly.

## Game reconstruction (Phase 9, on request)

For a game, the deepest output is a reconstruction package under
`work/<pkg>/reconstruction/`: the service architecture, every gameplay mechanic
with its real field and method names, a stage-by-stage runtime flow naming the
animation, VFX and sound that fires at each beat, the economy/meta/LiveOps
design, an honest unknowns ledger, and a compiling code skeleton whose constants
are either measured (`// [D]`) or explicitly open (`// TODO tune`).

It is driven by `references/game-reconstruction-guide.md` and runs in a
subagent — the recovered API surface is several megabytes and must never enter
the orchestrator's context.

Extraction and the metadata dump are **deterministic**: rerunning them on the
same package produces a byte-identical tree. The reconstruction documents are
authored, so wording varies; the file set, section structure, evidence tags and
every factual claim do not.

## Game content extraction (Unity)

When Phase 2 detects a Unity build, `unity-assets.sh` runs `unity-extract.py`
under an opt-in venv (UnityPy + numpy + Pillow) and extracts the game's content
into `work/<pkg>/game-assets/` — **grouped by the object it belongs to**, not
dumped flat:

- `entities/<Name>/` — one self-contained folder per game object: model, its
  pre-modelled fracture pieces, its textures, its material values, colliders,
  joints, rigidbody, animations, particle systems, a rendered `preview.png`, a
  machine-readable `entity.json` rebuild recipe and a human `README.md`.
- shared pools for cross-cutting assets: `textures/`, `sprites/` (with pivot,
  pixels-per-unit and 9-slice metadata), `audio/`, real `fonts/` (TTF/OTF),
  `levels/` (plus a derived mechanic-introduction curve and A/B ladder
  detection), `spine/`, `text/`.
- engine-wide capture: `materials.json`, `physics.json`, `shaders/` (real names
  and full property tables, grouped buy-vs-re-author), `particles/` (every
  module), `animations/` (clips + controllers), `ui/` (canvases and
  RectTransform trees), `scenes/`, `project-settings/` (with a README naming
  every value that differs from Unity's defaults), `ARCHITECTURE.md`.
- `unity-import/ImportExtracted.cs` — a Unity Editor script that rebuilds each
  entity as a prefab with its colliders, rigidbody and joints applied.
- `IMPORT.md` — what is directly usable, what was decoded from a lossy format,
  what needs re-authoring, and which importer flags to set by hand.

Only three things are genuinely unrecoverable from an IL2CPP release build:
MonoBehaviour/ScriptableObject **field values**, shader **HLSL**, and C#
**method bodies**. Everything else — including full prefab structure — comes
out. See `skills/clone-app/references/unity-asset-extraction-guide.md`.

Extracted art is reference material; the transferable output is the structure.

## Legal
For lawful use only — your own apps, authorized interoperability, security
research, or education. You are responsible for compliance.
