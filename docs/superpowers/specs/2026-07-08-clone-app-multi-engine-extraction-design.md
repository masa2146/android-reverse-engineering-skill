# clone-app Multi-Engine Asset & Mechanics Extraction — Design

**Date:** 2026-07-08
**Status:** Approved-for-implementation
**Scope:** `plugins/clone-app/` Phase 2 engine handling — a new engine-agnostic
dispatcher plus per-engine extraction modules for **Unity (il2cpp + mono)**,
**Godot**, and **Unreal Engine**. Introduces an isolated extraction venv.
**Trigger:** The current pipeline only detects Unity and its asset extraction is a
non-functional stub. The author wants real, quality asset **and** mechanics
extraction across all popular engines, without bloating the skill's context.

## Background

Today clone-app is architected for business apps; game support is a thin Unity-only
overlay. Three concrete limits block the author's goal:

1. **Asset extraction does not actually run.** `unity-assets.sh` wraps AssetRipper,
   whose current release is a GUI web-server with no one-shot CLI, so no
   sprite/audio/mesh/scene is ever extracted (only a manual-defer marker). Non-Unity
   apps only *count* drawables. OBB/`.pak`/`.pck` contents are never unpacked.
2. **Only Unity is detected.** `detect-unity.sh` returns `il2cpp | mono | none`.
   Unreal, Godot, and native games get no engine handling.
3. **Mechanics recovery is shallow for the common case.** Most shipping Unity games
   are il2cpp, whose method bodies compile to native ARM and are unrecoverable
   statically — only type signatures survive. There is no data-layer extraction and
   no escalation path.

This spec closes these gaps with a modular architecture that keeps the skill's
context small (progressive disclosure) and preserves the repo's honesty and
scripts-vs-rubrics conventions.

## Design principles

- **Engine-agnostic core, per-engine plug-in modules.** `SKILL.md` never contains
  any engine's details. A thin dispatcher detects the engine and loads *only* the
  matching engine's reference guide + scripts. Adding an engine = adding a module
  directory; the core is untouched. This is what keeps context from ballooning.
- **Uniform module contract.** Every engine module fills the same output contract,
  so the downstream Clone Build Spec assembler never needs to know which engine ran.
- **Tiered mechanics recovery.** Cheap, deterministic, no-infra extraction runs
  automatically (Layer 1). Expensive/noisy escalation (Layer 2, native disassembly)
  is user-gated. Device/root techniques (Layer 3, Frida) are a designed seam, not
  built now.
- **Honest coverage, never silent truncation.** Every module emits a machine-checkable
  coverage manifest and confidence-stamped mechanics; a `coverage-report.md`
  aggregates what was covered / partial / missing and *why*.
- **Automation decides the cheap path; the user decides the expensive one.** Engine
  detection and Layer-1 extraction are automatic. The user is consulted only at two
  gates: missing tool/dependency, and escalation to Layer 2.
- **Reference-only asset stance preserved.** Extracted art is copyrighted; the
  contract stamps it "reference only — recreate in the same style," never a
  ship-ready 1:1 copy. This design targets *analysis + faithful rebuild*, not a
  byte-identical clone.

## Architecture

### The dispatcher (engine-agnostic core)

Phase 2 of `SKILL.md` gains an engine-detection + dispatch step that carries no
engine specifics itself:

```
SKILL.md Phase 2
  └─ scripts/detect-engine.sh  →  { unity-il2cpp | unity-mono | unreal | godot | native | none }
       └─ loads ONLY the matching module:
            references/engines/<engine>-guide.md      (judgment rubric, on demand)
            scripts/engines/<engine>/extract-*.sh      (deterministic extractors)
```

`detect-engine.sh` subsumes today's `detect-unity.sh` (kept/refactored as the Unity
branch) and adds Unreal + Godot + native detection. Detection markers:

- **Unity** — `libunity.so`; `libil2cpp.so` + `global-metadata.dat` → `unity-il2cpp`;
  `assets/bin/Data/Managed/<Name>.dll` (direct child) → `unity-mono`. (Existing
  XAPK-aware, split-APK-aware logic from `detect-unity.sh` is retained.)
- **Unreal** — `libUE4.so`/`libUnreal.so`, `*.pak`, `*.uasset`/`*.uexp`,
  `AssetRegistry.bin`.
- **Godot** — `libgodot_android.so`/`libgodot.so`, `*.pck`, `assets/*.pck` or an
  embedded PCK in the binary, `project.binary`.
- **native** — none of the above but native `.so` game markers → flagged
  `not-recoverable` for mechanics, assets via generic resource listing only.

### Uniform module contract

Regardless of engine, a module writes these to `$WORK/`:

| Output | Contents |
|---|---|
| `mechanics-digest.md` | Recovered logic/rules/formulas + data-layer values, each **confidence-stamped**: `observed` (from near-source) / `inferred` (from data) / `signature-only` / `not-recoverable`. |
| `game-assets/` + `manifest.json` | Extracted textures/sprites/audio/meshes/scenes/prefabs/fonts + an inventory manifest with per-type counts and the *expected vs extracted* coverage ratio. |
| `netcode-recon.md` | Observed netcode/backend surface (Photon/PlayFab/Mirror/HTTP), same confidence stamps. Complements the existing `backend-recon.md`. |
| `coverage-report.md` | Aggregated: what was covered, what is partial, what is missing, and **why** (unsupported format, encrypted pak, il2cpp bodies, etc.). |

The Phase 8 Clone Build Spec assembler reads this contract only — no engine
branching in the assembler.

### Flow & decision gates

```
detect-engine
  → [dependency gate: if a required tool/venv is missing → PAUSE, ask install / proceed limited]
  → Layer-1 extraction (auto): assets + data + near-source mechanics
  → completeness self-check (coverage manifest)
  → [if mechanics gap AND unity-il2cpp: offer Layer-2 (Ghidra) → PAUSE, user decides]
  → write contract outputs + coverage-report.md
  → feed into clone-build-spec.md
```

The user is consulted at exactly two points (mirroring clone-app's existing
two-pause pattern): the **dependency gate** and the **Layer-2 escalation**.

## Per-engine module internals

### Unity (`unity-il2cpp`, `unity-mono`)

- **Assets (Layer 1):** Replace the non-functional AssetRipper stub in
  `unity-assets.sh` with a **UnityPy**-based extractor (runs in the extraction venv;
  real headless Python API). Extracts textures/sprites, audio, meshes, fonts,
  scenes, prefabs, and — critically for mechanics — **ScriptableObjects / balance
  tables / curve data** decoded to JSON. Writes `game-assets/` + `manifest.json`
  with expected-vs-extracted counts derived from the AssetBundle entry list.
- **Mechanics (Layer 1):** mono → extract `Assembly-CSharp.dll` + decompile with
  `ilspycmd` (near-source C#, `observed`). il2cpp → `il2cpp-dump.sh`
  (Il2CppInspectorRedux) type model (`signature-only`) + the data-layer values from
  UnityPy (`inferred`).
- **Mechanics (Layer 2, il2cpp only, opt-in):** Ghidra headless
  (`analyzeHeadless`) over `libil2cpp.so`, applying `global-metadata.dat` symbol
  names to label functions; best-effort decompiled bodies for the handful of
  gameplay-critical methods the user flags. Noisy; user-gated.

### Godot (`godot`)

- **Assets + mechanics (Layer 1):** `gdsdecomp` (Godot RE Tools) unpacks the `.pck`,
  decompiles GDScript to near-source (`observed`), and exports resources
  (`.tscn`/`.scn`/`.tres`, textures, audio). Godot is the highest-fidelity engine —
  both logic and assets recover cleanly. Encrypted PCKs (rare) are flagged in the
  coverage report.

### Unreal (`unreal`)

- **Assets (Layer 1):** `CUE4Parse` (or FModel CLI) extracts `.pak`/`.uasset` →
  textures, audio, meshes, and **DataTable** rows (the data layer). If the pak is
  AES-encrypted, the missing key is reported (coverage `missing: encrypted`) rather
  than failing silently.
- **Mechanics (Layer 1):** Blueprint bytecode dumped from `.uasset` via
  CUE4Parse/UAssetGUI (`inferred`); native C++ gameplay is `not-recoverable`
  statically and stamped as such.

## Dependency & venv strategy

- **stdlib-only stays for core + test scripts.** `detect-engine.sh`, the dispatcher,
  manifest/coverage generators, and all tests remain stdlib-only, offline,
  fixture-driven.
- **An isolated, opt-in extraction venv** carries the heavy Python tooling.
  `scripts/setup-extraction-venv.sh` creates `.venv-extraction/` (git-ignored) and
  installs `requirements-extraction.txt` (UnityPy + Python glue). Extractors that
  need it call the venv's interpreter explicitly.
- **Non-Python tools go through the dependency gate**, not pip: Ghidra,
  CUE4Parse/FModel, gdsdecomp, `dotnet`, `ilspycmd`. Each extractor checks for its
  tool (or `$TOOL_CLI` override), and on absence **pauses with concrete install
  guidance** (command, size, time) + a `limited:` proceed option — the existing
  Unity dependency-gate pattern, generalized.
- This **consciously reverses** the prior spec's "UnityPy is out of scope because it
  needs pip" constraint (`2026-07-04-clone-app-unity-tooling-fixes-design.md`), by
  isolating pip usage in a dedicated venv while keeping shipped core/test scripts
  stdlib-only.

## Implementation decomposition

Each engine is an independent module and gets its own spec→plan→implementation
cycle. Build order (cheapest-highest-value first):

1. **Engine-agnostic core** — `detect-engine.sh`, dispatcher wiring in `SKILL.md`
   Phase 2, the uniform contract + `coverage-report.md` generator, venv bootstrap,
   `references/engines/` + `scripts/engines/` layout, fixtures/tests scaffold.
2. **Unity module** — extend existing scripts; swap the AssetRipper stub for UnityPy;
   add the Layer-2 Ghidra escalation.
3. **Godot module** — `gdsdecomp` extractor (easiest, highest fidelity).
4. **Unreal module** — `CUE4Parse` extractor (heaviest; AES-key handling).

## Out of scope

- **Layer 3 (Frida dynamic analysis).** Designed as a pluggable seam in the contract,
  but not implemented — requires emulator + root infrastructure.
- **Cocos2d-x, GameMaker, Defold, and other second-tier engines.** The `native`
  branch gives them generic resource listing only.
- **Shipping extracted assets.** Assets are reference-only; the build stage recreates
  in-style. No byte-identical/1:1 asset reproduction.
- **`clone-build` changes.** This spec stops at producing the extraction contract +
  build spec; consuming it in the build stage is separate work.

## Test plan

Following the repo pattern (offline, fixture-driven, stdlib-only tests):

1. `test-detect-engine.sh` — tiny fixture packages for unity-il2cpp/unity-mono/
   unreal/godot/native/none assert the correct classification (extends
   `test-detect-unity.sh`).
2. Per-engine extractor tests inject a `$TOOL_CLI=/no/such/bin` and assert the
   dependency-gate exit code + guidance text (no network, no real tool needed).
3. `test-coverage-report.sh` — a synthetic manifest with known expected/extracted
   counts asserts the correct covered/partial/missing rollup.
4. `test-skill-phases.sh` — the Phase 2 dispatcher edit adds, does not remove,
   required strings.
5. `smoke-structure.sh` — new engine scripts present + executable, `references/engines/`
   guides present, venv bootstrap script present.
6. `run-all.sh` — full suite green.
7. Manual per engine: one real game each (a Godot `.pck`, a Unity il2cpp XAPK, an
   Unreal `.pak` game) run end-to-end; verify `game-assets/`, `mechanics-digest.md`,
   and `coverage-report.md` are populated with honest coverage ratios.

## Deliverables (core module — subsequent engines separately)

- `plugins/clone-app/skills/clone-app/scripts/detect-engine.sh`
- `plugins/clone-app/skills/clone-app/scripts/setup-extraction-venv.sh` +
  `requirements-extraction.txt`
- `plugins/clone-app/skills/clone-app/scripts/engines/` + `references/engines/` layout
- Coverage/manifest generator + `coverage-report.md` template
- `plugins/clone-app/skills/clone-app/SKILL.md` Phase 2 dispatcher
- Tests + fixtures for detection, dependency gates, coverage rollup
- This design note.
