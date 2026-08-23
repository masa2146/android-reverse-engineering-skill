---
description: Analyze a Google Play app to assess cloning it — download the APK, reverse engineer the tech stack and APIs, analyze app-store presence, estimate AI-assisted build effort and infrastructure cost, judge market viability, and optionally generate an implementation plan. Use when the user gives a Google Play URL or package name and wants a clone feasibility analysis, effort estimate, or tech-stack breakdown. 中文触发词：克隆应用、复刻这个app、分析可行性、估算开发量、克隆可行性分析
trigger: clone app|clone this app|clone feasibility|feasibility analysis|estimate effort to build|reverse engineer and clone|analyze this play store app|can I clone|克隆应用|复刻|可行性分析
---

# Clone App — Feasibility & Effort Analysis

Take a Google Play URL (or package name), reverse engineer the app, analyze its
market, estimate AI-assisted clone effort and infrastructure cost, and produce a
viability report. If the user approves, hand off to the writing-plans skill to
generate a full implementation plan.

This skill orchestrates 10 phases (0–9). Deterministic steps are factored into helper
scripts under `${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/`. Reverse
engineering reuses the sibling `android-reverse-engineering` plugin's scripts.

## Legal note
Only analyze apps you are authorized to (your own, or for lawful interoperability
/ research). Surface this to the user if intent is unclear. Do not proceed for
clearly infringing intent.
Pixel-perfect cloning and extracting copyrighted assets (especially game art via
AssetRipper) is high-risk. Proceed only for authorized use; the build spec
recreates assets in the same style and treats extracted assets as reference, not
ship-ready, outside authorized contexts.

## Phase 0: Input & Validation

Extract the package name:
```bash
PKG="$(bash ${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/extract-package.sh "<user-input>")"
```
If it exits non-zero, ask the user for the package name directly, then re-run.

Create the working dir with its standard three-layer layout:
```bash
WORK="$(bash ${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/init-workdir.sh "$PKG")"
# -> ./work/<pkg>/  containing deliverables/  extracted/  raw/  README.md
```
The split is by what the reader does with it — **deliverables/** is written for a
person, **extracted/** is clean data for a machine, **raw/** is regenerable
intermediates. Write every artifact into the right layer; the paths below say
which. Nothing in `raw/` is ever deleted automatically (Phases 8 and 9 read back
from it) — the user clears it with `clean-workdir.sh` when finished.

If the user points at an older flat working directory, migrate it first:
`bash ${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/migrate-workdir.sh <dir>`
(add `--dry-run` to preview; it moves, never deletes, and reports anything it
did not recognise).

## Phase 1: APK Download

```bash
APK="$(bash ${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/download-apk.sh "$PKG" "$WORK/raw/package")"
```
The script downloads via `apkeep` (default source `apk-pure`; no auth, no
JavaScript, handles XAPK split bundling) and prints the path (`app.apk` or
`app.xapk`). It needs the `apkeep` binary on PATH — install with
`brew install apkeep` (or `cargo install apkeep`). If it exits non-zero,
`apkeep` may be missing or the app isn't on that source (try another with
`CLONE_APP_APKEEP_SOURCE=apk-combo`) — tell the user the download failed and
ask for a local APK/XAPK path; set `APK` to that path.

## Phase 2: Reverse Engineering (probe → dispatch → consume)

RE runs inside an **isolated subagent** so the decompiled sources never flood
this orchestrator's context. The subagent prefers the
`android-reverse-engineering` **skill** and falls back to that plugin's bash
**scripts**. Either way it writes the same digest files to `$WORK/`, defined
in `${CLAUDE_PLUGIN_ROOT}/skills/clone-app/references/re-digest-contract.md`.

### Phase 2a — Probe

```bash
RE="$(bash ${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/resolve-re-scripts.sh 2>/tmp/re-err)"; RC=$?
```
- `RC == 0` → the RE **scripts** are on disk (fallback is available). If it
  printed a `WARNING:` about bash version, the scripts need **bash 4+**
  (macOS ships 3.2; `${VAR,,}` fails as "bad substitution") — install one with
  `brew install bash` before the script-fallback branch can succeed.
- Check your own available-skills list for `android-reverse-engineering` →
  is the RE **skill** registered?

### Phase 2b — Engine dispatch

Classify the package by game engine and load **only** the matching module, so no
engine's tooling docs bloat this orchestrator's context.

```bash
ENGINE="$(bash ${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/detect-engine.sh "$APK")"
# → unity-il2cpp | unity-mono | unreal | godot | native | none
```

- `unity-il2cpp` / `unity-mono` → continue to the Unity tool dependency gate below.
- `unreal` / `godot` → load that engine's guide under
  `${CLAUDE_PLUGIN_ROOT}/skills/clone-app/references/engines/` when its module lands
  (not yet implemented); until then treat as `limited:<engine>-not-implemented`.
- `native` → mechanics `not-recoverable`; generic resource listing only.
- `none` → non-game app; use the standard non-Unity design-capture path.

Whatever engine runs, its module fills the uniform contract in
`${CLAUDE_PLUGIN_ROOT}/skills/clone-app/references/engines/module-contract.md`
(`mechanics-digest.md`, `game-assets/` + `manifest.json`, `netcode-recon.md`, and a
`coverage-report.md` produced by
`python3 ${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/gen-coverage-report.py <manifest.json> --out $WORK/extracted/coverage-report.md`).
The downstream build spec reads `coverage-report.md` — never assume full coverage.

### Phase 2c — Unity tool dependency gate (run after engine dispatch, before the RE subagent dispatch)

Classify the build and confirm the extraction tooling is present, so the cost of
a missing tool is surfaced **before** the RE subagent runs — not buried in a
silent `limited:` digest afterward.

```bash
UNITY="$(bash ${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/detect-unity.sh "$APK")"   # il2cpp | mono | none
has_venv()   { bash ${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/setup-extraction-venv.sh >/dev/null 2>&1; }
has_dotnet() { command -v dotnet >/dev/null 2>&1; }
has_il2cpp() { command -v "${IL2CPP_INSPECTOR_CLI:-Il2CppInspector}" >/dev/null 2>&1; }
has_ilspy()  { command -v ilspycmd >/dev/null 2>&1; }
```

If `UNITY` is `none`, set `UNITY_TOOLS=n/a` and skip the rest of this gate.
Otherwise:

| Build | Asset + content extraction (primary) | Type-model tooling (secondary) |
|---|---|---|
| `il2cpp` | **extraction venv** (`setup-extraction-venv.sh` → UnityPy, numpy, Pillow) | `.NET` runtime (`dotnet`) **+** `Il2CppInspector` (Il2CppInspectorRedux) |
| `mono`   | **extraction venv** (same) | `.NET` runtime (`dotnet`) **+** `ilspycmd` |

**AssetRipper is not required** — `unity-assets.sh` extracts with UnityPy.
`ASSETRIPPER_CLI` is an optional supplement only; its absence costs nothing.

> **Reality check for `il2cpp`:** C# method bodies are compiled to native ARM and
> are unrecoverable **regardless of tools**. The IL2CPP tool only recovers
> class/method/field *signatures* — and the class inventory is recoverable from
> `MonoScript` records by the extractor anyway. What genuinely rides on the
> IL2CPP dump is the field/enum type model.

**If a required tool is missing → PAUSE and ask the user** (do not degrade
silently). Tell them, concretely:
- the build type, and that `il2cpp` method bodies are unrecoverable either way;
- what each missing piece loses:
  - **extraction venv absent → no game content at all**: no meshes, textures,
    sprites, materials, shaders, particles, animations, fonts, levels, scenes,
    prefab structure or project settings. This is the expensive one.
  - `dotnet`/`Il2CppInspector` absent → no field/enum type model in
    `unity-digest.md`.
- the exact commands + cost:
  - `bash ${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/setup-extraction-venv.sh`
    — local venv, ~150 MB, no sudo
  - `brew install --cask dotnet-sdk` — .NET, ~1 GB, **sudo** (user-run via `!`)
  - Il2CppInspectorRedux: download `Il2CppInspectorRedux.CLI-osx-arm64.zip` from
    https://github.com/LukeFZ/Il2CppInspectorRedux/releases, unzip, export
    `IL2CPP_INSPECTOR_CLI=<path>`
  - `brew install ilspycmd` (mono decompile)
- then ask: **install now, or proceed limited?**

Set `UNITY_TOOLS=full` if everything the user wants is present (or they just
installed it), else `UNITY_TOOLS=limited:<reason>` (e.g.
`limited:unity-no-unitypy`, `limited:unity-no-dotnet`). Pass `$UNITY` and
`$UNITY_TOOLS` to the Phase 2d subagent. Proceeding `limited:` is only valid once
the user has acknowledged the cost.

Pick the branch:

| RE skill registered | RE scripts on disk (`RC`) | Branch |
|---|---|---|
| yes | any | **re-skill** |
| no | 0 | **direct-scripts** |
| no | 1 | **stop** — show the `/tmp/re-err` resolver error and halt |

### Phase 2d — Dispatch the subagent

Dispatch one subagent (Agent tool, `general-purpose` type — it can both invoke
skills and run bash). Pass it: `$PKG`, `$APK`, `$WORK`, the chosen **branch**,
the resolved `$RE` scripts dir, the Phase 2c gate's `$UNITY` and `$UNITY_TOOLS`,
and the path to `re-digest-contract.md`. Its instructions:

Tell the subagent its clone-app scripts dir is
`${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/` (pass it explicitly as `$CA`).

1. **Run RE per branch.**
   - **re-skill:** invoke the android-reverse-engineering skill on `$APK`,
     output dir `$WORK/raw/decompiled` — run its full workflow (fingerprint, deps,
     decompile, Kotlin-name recovery if Kotlin, API extraction incl. Tier-2).
   - **direct-scripts:** run, in order, reading each output before the next:
     `bash "$RE/fingerprint.sh" "$APK"`, `bash "$RE/check-deps.sh"`
     (install required deps via `bash "$RE/install-dep.sh" <dep>`; ask before
     optional vineflower/dex2jar), `bash "$RE/decompile.sh" -o "$WORK/raw/decompiled" "$APK"`
     (add `--deobf` if obfuscation is heavy), `bash "$RE/recover-kotlin-names.sh"
     "$WORK/raw/decompiled/sources" "$WORK/raw/decompiled/names/"` if Kotlin, then
     `bash "$RE/find-api-calls.sh" "$WORK/raw/decompiled/sources"`.
2. **Capture design (Unity-aware).** `$UNITY` (`il2cpp|mono|none`) and
   `$UNITY_TOOLS` (`full` | `limited:<reason>`) were resolved by the Phase 2c gate
   — use them, do not re-run `detect-unity.sh`. After decompile:
   - **Non-Unity (`none`):** run
     `python3 "$CA/extract-design.py" "$WORK/raw/decompiled" --package "$PKG" --out "$WORK/extracted/design-tokens.json" --digest "$WORK/extracted/design-digest.md"`
     per `design-capture-guide.md`.
   - **Unity (both `il2cpp` and `mono`) — content extraction, always run first:**
     `bash "$CA/unity-assets.sh" "$APK" "$WORK/extracted/game-assets"`. It writes
     `manifest.json` itself — do not hand-inventory the directory. Then
     `python3 "$CA/gen-coverage-report.py" "$WORK/extracted/game-assets/manifest.json" --out "$WORK/extracted/coverage-report.md"`.
     Read `$WORK/extracted/game-assets/IMPORT.md`, `manifest.json` and
     `project-settings/README.md` — never the extracted files themselves.
     The output contract is `unity-asset-extraction-guide.md`.
   - **Unity (`il2cpp`) — API surface, always run, needs no .NET:** locate
     `global-metadata.dat` (under `$WORK/raw/decompiled` or unzipped from `$APK`) and run
     `python3 "$CA/il2cpp-metadata-dump.py" <metadata> --out "$WORK/extracted/api-surface.json" --markdown "$WORK/extracted/api-surface.md"`.
     This recovers **every type, field, property and method name** in the game
     assemblies — the skeleton of every system — with the stdlib alone. It is the
     single highest-value artifact for reconstructing mechanics: read
     `api-surface.md` for the game assemblies (`Core`, `Assembly-CSharp`,
     `<Game>.*`) and cite it in the digest.
   - **Unity (`il2cpp`) — optional deeper type model:** if `dotnet` +
     `Il2CppInspector` are present, also run
     `bash "$CA/il2cpp-dump.sh" <so> <metadata> "$WORK/raw/il2cpp/unity-out"` for field/enum
     *types* (the metadata dump gives names, not resolved types). Write
     `$WORK/extracted/unity-digest.md` (type model + netcode) per `unity-re-guide.md`.
     Method **bodies** remain unrecoverable either way.
   - **Unity (`mono`) — type model:** extract `assets/bin/Data/Managed/*.dll`
     from `$APK` (for an XAPK, from the nested `base.apk`) into `$WORK/raw/il2cpp/managed/`,
     then `ilspycmd "$WORK/raw/il2cpp/managed/Assembly-CSharp.dll" -o "$WORK/raw/il2cpp/unity-out"`
     (repeat for other DLLs of interest; near-source C#); write
     `$WORK/extracted/unity-digest.md` per `unity-re-guide.md`.
   - **Do not claim what was not extracted.** `manifest.json` notes and
     `coverage-report.md` are the honest record; carry their gaps into the
     digest instead of implying full coverage. In particular, only three things
     are genuinely unrecoverable — MonoBehaviour/ScriptableObject field values,
     shader HLSL, and IL2CPP method bodies. Anything else missing is a tooling
     gap to report, not a limitation to assert.
   - If `$UNITY_TOOLS` is `limited:<reason>`, **skip the missing tool's step**
     (the user acknowledged the cost at the Phase 2c gate), write whatever is
     recoverable, and set `RE Method: $UNITY_TOOLS` (e.g.
     `limited:unity-no-dotnet`, `limited:unity-no-assetripper`). If
     `$UNITY_TOOLS` is `full`, run every tool above.
3. **Framework guard:** if the fingerprint is Flutter / React Native / Cordova
   / Xamarin, Java decompile is shallow — produce a partial digest, set
   `RE Method: limited: <framework>`, payloads may be empty.
4. **Extract** the Tier-1 endpoint inventory and Tier-2 payloads for **auth,
   payment/checkout, and the 1–2 core feature endpoints** (not every endpoint).
5. **Write** `$WORK/extracted/re-digest.md`, `$WORK/extracted/payloads.json`, `$WORK/extracted/re-summary.txt`
   exactly per `re-digest-contract.md`. Also produce `$WORK/extracted/design-tokens.json`
   and `$WORK/extracted/design-digest.md` (plus `$WORK/extracted/unity-digest.md` and
   `$WORK/extracted/game-assets/` when Unity).
6. **Return** the contents of `$WORK/extracted/re-summary.txt` plus a short `design-summary`
   (and, when Unity, a `unity-summary` quoting the extracted per-type counts, the
   entity count, the non-default engine settings, and the coverage gaps) and the
   digest file paths — **never** raw decompiled sources, resources, or assets.

If the subagent fails, retry once; if it still fails and the **direct-scripts**
branch is available (i.e. the Phase 2a probe returned `RC == 0`), re-dispatch on
that branch; otherwise stop and report.

### Phase 2e — Consume

Read `$WORK/extracted/re-summary.txt` (the only RE text in this context). From it you have:
framework, HTTP stack, host counts, endpoint count, key-flow names, secrets
count, and the RE method. Read `$WORK/extracted/re-digest.md` or `$WORK/extracted/payloads.json`
**on demand** when a later phase needs detail. Keep the summary in context for
Phases 3–8.

## Phase 3: Store Analysis

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/scrape-play-store.py "$PKG" > "$WORK/extracted/store/play.json"
```
Read `play.json` for rating, rating_count, installs, category, developer, updated.
Use the `title` to check iOS:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/check-appstore.py "<title>" > "$WORK/extracted/store/appstore.json"
```
If Play scrape returned mostly nulls (page layout changed), fall back to a web
search for the app's metrics and note the source. App Store absence is fine —
continue with Google Play data only.

Download the screenshots for visual ground truth:
```bash
mkdir -p "$WORK/extracted/store/screenshots"
python3 - "$WORK/extracted/store/play.json" "$WORK/extracted/store/screenshots" <<'PY'
import json, sys, os, urllib.request
play, outdir = sys.argv[1], sys.argv[2]
urls = (json.load(open(play)).get("screenshot_urls") or [])
man = []
for i, u in enumerate(urls, 1):
    dest = os.path.join(outdir, f"{i:02d}.png")
    try:
        urllib.request.urlretrieve(u, dest); man.append({"order": i, "url": u, "path": dest})
    except Exception as e:
        print(f"WARN: screenshot {i} failed: {e}", file=sys.stderr)
json.dump(man, open(os.path.join(outdir, "manifest.json"), "w"), indent=2)
print(f"saved {len(man)} screenshots")
PY
```
If `screenshot_urls` is null/empty (layout change), note it and rely on
`design-tokens.json` + a web image search for visual reference.

## Phase 4: Stack Recommendation

Read `${CLAUDE_PLUGIN_ROOT}/skills/clone-app/references/stack-recommendation-guide.md`.
Using the RE results + store data, present 2-3 stack options as a table and ask
the user to choose. **Wait for the user's choice before Phase 5.** Lock it.

## Phase 5: Effort & Cost Estimation

Read `${CLAUDE_PLUGIN_ROOT}/skills/clone-app/references/effort-estimation-guide.md`
and `infra-cost-guide.md`. Build:
- read `$WORK/extracted/payloads.json`; the endpoint count and the payload complexity of
  the key flows size the backend work,
- the feature list + backend surface → AI-Sprint effort table (min-max total,
  uncertainty band; widen the band when RE Method is `limited:`),
- the MVP/Growth/Scale monthly infra cost table.
Base both on the **user-selected stack** from Phase 4.

## Phase 6: Market Viability Report

Read `${CLAUDE_PLUGIN_ROOT}/skills/clone-app/references/report-template.md`.
Fill every section from the data gathered. For market analysis (competitors,
market size), use web search as needed. Produce a GO / CONDITIONAL GO / NO GO
verdict tying effort + cost against market opportunity.
Include a **Backend API Surface** section: summarize the Tier-1 inventory from
`$WORK/extracted/re-digest.md` and the key-flow payloads from `$WORK/extracted/payloads.json` (host
list, endpoint count, auth model, and the auth/payment/core request+response
shapes). If RE Method was `limited:`, say so and note the reduced confidence.
Also fill the **Design System** section from `$WORK/extracted/design-tokens.json` and
`$WORK/extracted/design-digest.md` per `report-template.md`. For game engines, also fill the **Game Content** section (§4b) from
`$WORK/extracted/game-assets/manifest.json`, `coverage-report.md`, `IMPORT.md`,
`levels/level-analysis.json`, `project-settings/README.md` and `shaders/README.md`
per `report-template.md`.

Write the report:
```
$WORK/deliverables/clone-report-<YYYY-MM-DD>.md
```
(Use the actual run date.) Show the user a concise summary + the verdict.

## Phase 7: Decision Gate

Ask: "Feasibility report saved to `$WORK/deliverables/clone-report-<date>.md`. Proceed to
build the implementation plan? (This runs the deep **fidelity pass** — full
API payloads, in-app logic, navigation graph, and an inferred backend design —
and produces a second report.)"
- **Yes** → run Phase 8: the fidelity pass, then assemble the build spec and
  hand off to `superpowers:writing-plans`.
- **No** → stop; the feasibility report stands on its own. The fidelity pass
  (and its token cost) is never incurred.

**When a game engine was detected**, offer the deeper option in the same
question: "…or go all the way and produce the **full reconstruction** —
architecture, every mechanic, the stage-by-stage runtime flow with the animation
/VFX/sound that fires at each beat, the meta and LiveOps design, an honest list
of what is not recoverable, and a compiling code skeleton (Phase 9)."
- **Reconstruction** → run Phase 8, then Phase 9.
Phase 9 is the most expensive phase in the skill and the most useful for a game;
never run it without the user asking.

## Phase 8: Fidelity Pass + Build Spec

Read `${CLAUDE_PLUGIN_ROOT}/skills/clone-app/references/fidelity-pass-guide.md`.

### Phase 8a — Fidelity subagent (deep extraction)

Dispatch one subagent (Agent tool, `general-purpose`). It reuses what Phase 2
already decompiled to `$WORK/raw/decompiled` — **no re-download, no re-decompile**. Pass
it `$PKG`, `$WORK`, the clone-app scripts dir `$CA`
(`${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/`), and the paths to
`fidelity-pass-guide.md`, `logic-capture-guide.md`, `backend-recon-guide.md`.
Its instructions:

1. **Full Tier-2 payloads.** Extend `$WORK/extracted/payloads.json` so every first-party
   endpoint carries request/response/headers (third-party stays Tier-1).
2. **In-app logic.** Run
   `python3 "$CA/extract-logic.py" "$WORK/raw/decompiled" --out "$WORK/extracted/logic-signals.json"`,
   then write `$WORK/extracted/logic-digest.md` per `logic-capture-guide.md`.
3. **Navigation graph.** Run
   `python3 "$CA/extract-nav-graph.py" "$WORK/raw/decompiled" --out "$WORK/extracted/nav-graph.json"`.
4. **Backend recon.** Write `$WORK/extracted/backend-recon.md` per `backend-recon-guide.md`.
5. **Unity (if RE Method indicated Unity).** Deepen `$WORK/extracted/unity-digest.md` with
   game mechanics / formulas per `unity-re-guide.md`.
6. **Return** a short fidelity summary + the artifact paths — never raw sources.

If the subagent fails, retry once; if it still fails, continue with whatever
artifacts exist and note the gap in the fidelity report.

### Phase 8b — Fidelity report

Write `$WORK/deliverables/fidelity-report-<YYYY-MM-DD>.md` (actual run date): summarize the
logic digest, navigation graph, full API surface, and backend recon, each with
its confidence. This is a standalone report alongside the feasibility one.

### Phase 8c — Build spec

Read `${CLAUDE_PLUGIN_ROOT}/skills/clone-app/references/clone-build-spec-template.md`.
Assemble `$WORK/deliverables/clone-build-spec.md`, filling every section from the artifacts:
- §2 from `$WORK/extracted/design-tokens.json` (+ `design-digest.md`),
- §3 one entry per screen, each paired with `$WORK/extracted/store/screenshots/NN.png`, plus its
  logic from `$WORK/extracted/logic-digest.md`,
- §3b user-flow diagrams from `$WORK/extracted/logic-digest.md`,
- §4 from `$WORK/extracted/nav-graph.json`,
- §5 from `$WORK/extracted/payloads.json` (full Tier-2), §5b + §6 from `$WORK/extracted/backend-recon.md`,
- §7 asset inventory from `$WORK/raw/decompiled` (or `$WORK/extracted/game-assets/` for Unity),
- §8 acceptance criteria per screen + flow,
- §10 absolute paths to every `$WORK/` artifact.
Use the **Game variant** sections when RE Method indicated Unity.

Then invoke `superpowers:writing-plans`, passing `$WORK/deliverables/clone-build-spec.md` as
the spec and citing BOTH `$WORK/deliverables/clone-report-<date>.md` and
`$WORK/deliverables/fidelity-report-<date>.md` as reference. The build spec + `$WORK/` is the
standalone input — a fresh session with it can build an exact / near-exact clone.

## Phase 9: Game Reconstruction (games only, on request)

Read `${CLAUDE_PLUGIN_ROOT}/skills/clone-app/references/game-reconstruction-guide.md`.
Turns the extracted artifacts into a buildable reconstruction: architecture,
mechanics, runtime flow, meta/LiveOps design, an unknowns ledger, and a code
skeleton. Requires Phase 2's game-content extraction and, for IL2CPP builds,
`$WORK/extracted/api-surface.json`.

### Phase 9a — Dispatch the reconstruction subagent

**This must run in a subagent.** `api-surface.md` is 4–10 MB on a real game;
reading it in this context would end the session. Dispatch one subagent (Agent
tool, `general-purpose`) and pass it: `$PKG`, `$WORK`, the engine, and the path
to `game-reconstruction-guide.md`. Its instructions:

1. **Follow the guide exactly** — the output structure, the evidence tags
   (`[D]` data / `[S]` signature / `[I]` inferred / `[X]` not recoverable), the
   working order, and the honesty rules are all specified there.
2. **Never read `api-surface.md` or `api-surface.json` whole.** Use the query
   recipes in the guide to pull one subsystem at a time.
3. **Write** `$WORK/deliverables/reconstruction/` — `README.md`, `01-ARCHITECTURE.md`,
   `02-GAMEPLAY-MECHANICS.md`, `03-FLOW.md`, `04-META-LIVEOPS.md`,
   `05-UNKNOWNS.md`, and `code/`.
4. **Return** only: the file list with line counts, the count of `[D]`/`[S]`
   claims and `// TODO tune` markers, the subsystems covered, and anything it
   could not cover. **Never** the document contents or any source.

If the subagent fails, retry once; if it still fails, keep whatever it wrote and
report the gap — a partial reconstruction is useful, a silent one is not.

### Phase 9b — Report

Tell the user what landed, and be explicit about the split: the **design** is
recovered, the **balance** is not. Point at `05-UNKNOWNS.md` as the tuning
backlog and at `code/README.md` for the measured project settings to apply
first. Add a Reconstruction section to the feasibility report linking the
package.

## Error Handling Summary
| Scenario | Action |
|---|---|
| Package not in URL | ask user for package name |
| Flat pre-layout working dir | run `migrate-workdir.sh <dir>` first; it moves, never deletes |
| User asks to reclaim disk | `clean-workdir.sh <workdir>` removes `raw/` only; never call it unprompted |
| Download fails 3× | ask for local APK path |
| RE skill + scripts both missing | show resolver error, stop |
| RE subagent fails | retry once, then fall back to direct-scripts branch; else stop |
| Subagent returned no digest files | re-dispatch once; if still missing, stop and report |
| Flutter/RN/Cordova/Xamarin | warn, continue with limited RE |
| App Store not found | continue Google Play only |
| Play scrape returns nulls | web-search fallback, note source |
| Heavy obfuscation | add uncertainty band, note in report |
| writing-plans unavailable | write the plan as Markdown manually |
| Unity build detected | run the content extraction, then the IL2CPP metadata dump (no .NET needed) |
| Unity tool missing | Phase 2c gate pauses + asks the user (install vs limited); `RE Method: limited:<reason>` only after consent |
| Extraction venv unavailable | `unity-assets.sh` exits 3 with install guidance — no game content is produced; surface this at the Phase 2c gate, never proceed silently |
| `unity-assets.sh` exits 4 | extraction ran but produced no manifest — report as a failure, do not treat an empty `game-assets/` as coverage |
| Entity has no mesh | check `geometry_status` in its `entity.json`: `builtin-primitive` / `procedural` / `external-reference` are findings, not failures |
| Phase 9 requested for a non-game | decline — reconstruction needs a game engine's extracted content; the Phase 8 build spec is the right output |
| Phase 9 subagent fails | retry once, then keep the partial `reconstruction/` and name the missing documents |
| `api-surface.json` missing | Phase 9 still runs from assets alone, but mechanics drop to `[D]`-only; say so in the reconstruction README |
| No screenshots on Play | note it, rely on design-tokens + web image search |
| Phase 7 = No | stop after feasibility report; skip the fidelity pass |
| Fidelity subagent fails | retry once, then continue with partial artifacts and note the gap |
| extract-logic/nav-graph finds nothing (Flutter/RN) | note low confidence, lean on screenshots + API contract |
