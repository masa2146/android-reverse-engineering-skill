# Unity Reverse-Engineering Guide

Unity ships game logic as native IL2CPP or as managed Mono assemblies. jadx is
blind to IL2CPP — detect the build first with `detect-unity.sh`.

## IL2CPP (`detect-unity.sh` → `il2cpp`)

Inputs: `lib/<abi>/libil2cpp.so` + `assets/bin/Data/Managed/Metadata/global-metadata.dat`.
Run `il2cpp-dump.sh <so> <metadata> <out>` (wraps **Il2CppInspectorRedux**,
https://github.com/LukeFZ/Il2CppInspectorRedux). The CLI release is
**framework-dependent on .NET 10** (a ~2 MB apphost, not self-contained) — install
the runtime first: `brew install --cask dotnet-sdk` (sudo), then download
`Il2CppInspectorRedux.CLI-osx-arm64.zip` from the releases page and export
`IL2CPP_INSPECTOR_CLI=<path/to/Il2CppInspector.Redux.CLI>`.

**Recoverable:** class / method / field / enum signatures, type hierarchy,
serialized fields, network/RPC type shapes → data model + feature inventory.
**Not recoverable:** C# method *bodies* (compiled to native ARM in the .so).

## Mono (`detect-unity.sh` → `mono`)

Inputs: `assets/bin/Data/Managed/*.dll` (real .NET assemblies). Decompile to
near-source C# with `ilspycmd` (ILSpy CLI): `ilspycmd Assembly-CSharp.dll -o <out>`.
Best case — full logic recovered.

## Assets (both branches)

`unity-assets.sh <apk> <out>` runs **`unity-extract.py` under the opt-in
extraction venv** (UnityPy + numpy + Pillow, created by
`setup-extraction-venv.sh`). It really extracts — meshes, textures, sprites,
materials, shaders, particles, animations, audio, fonts, levels, scenes, prefab
structure and project settings — grouped per entity and ready to import. The
output contract is `unity-asset-extraction-guide.md`.

**AssetRipper is no longer required.** Its current release
(`AssetRipper.GUI.Free`) is a web-server GUI with no one-shot CLI, so it could
never extract anything unattended; it stays available as an *optional
supplement* via `ASSETRIPPER_CLI` for scene/shader reconstruction UnityPy does
not attempt.

Exit codes: `0` success (with a real `manifest.json`) · `2` usage / missing
package · `3` UnityPy unavailable, with venv install guidance · `4` extraction
failed. There is no path that exits 0 without extracting.

### Recoverability matrix

The rule: **Unity engine types ship their type tree, so every field is readable.
Only user types (MonoBehaviour / ScriptableObject) are stripped in an IL2CPP
release build.**

**Genuinely NOT recoverable — exactly three things:**

| Data | Why |
|---|---|
| MonoBehaviour / ScriptableObject field values | type trees stripped; `read_typetree()` raises. Costs you balance tables, tuning configs, LiveOps parameters. Class *names* survive via `MonoScript`. |
| Shader HLSL / compiled bytecode | compiled per platform |
| C# method bodies | AOT-compiled into `libil2cpp.so` |

**Everything else IS recovered, and the extractor writes all of it:**

| Data | Where it lands |
|---|---|
| Meshes (+ pre-modelled fracture pieces) | `entities/<E>/*.obj`, `broken/` |
| Textures, with per-file lossless-vs-decoded flag | `textures/` + `texture-formats.json` |
| Sprites with pivot / PPU / 9-slice border | `sprites/` + `sprite-meta.json` |
| Materials: every float, colour, keyword, texture slot | `materials.json`, and per entity |
| **Shader interfaces**: real name, full property table, tags, keywords, fallback | `shaders/*.json` + a buy-vs-re-author README |
| **Particle systems**: every module + renderer | `particles/*.json` |
| **Colliders** (box/sphere/capsule/mesh geometry) and **joints** (limits, drives, break force) | `entities/<E>/entity.json` |
| Rigidbody, PhysicMaterials, PhysicsManager | `physics.json`, `project-settings/physics.json` |
| **Animation clips** (legacy + Mecanim Streamed/Dense/Constant) and **AnimatorControllers** (TOS, layers, state machines) | `animations/` |
| **Real TTF/OTF fonts** + kerning/metrics | `fonts/` + `fonts.json` |
| UI: canvases + full RectTransform trees | `ui/*.json` |
| **Project settings**: physics, time, quality tiers, graphics, tags + 32 layer names, audio, input, render, lightmap, navmesh, build | `project-settings/` + a README naming what differs from Unity defaults |
| Scene hierarchies, lights, cameras, audio sources | `scenes/` |
| Level database + mechanic-introduction curve + A/B ladder detection | `levels/` + `level-analysis.json` |
| C# class inventory (no IL2CPP tooling needed) | `ARCHITECTURE.md` |

`PlayerSettings` may fail to parse when the build's layout is newer than
UnityPy's type tree; that failure is recorded and the APK manifest is the
fallback for identity fields.

**Prefab structure IS recoverable** — hierarchy plus every engine component and
its exact values. Only the custom script field values are missing. Never write
"prefab structure not recoverable" in a report.

`unity-import/ImportExtracted.cs` ships with each extraction: drop it in
`Assets/Editor/`, run **Tools → Clone App → Import Extracted Assets**, and it
rebuilds prefabs with meshes, materials, colliders, rigidbody and joints applied.

For layout reference the Play screenshots in `$WORK/screenshots/` still help,
but they are no longer the primary source — the extracted `ui/` trees are.

## Dependency gate (Phase 2c) vs graceful degradation

The Phase 2c Unity tool gate runs **before** the RE subagent. Its primary check
is now the **extraction venv / UnityPy**, because that is what determines
whether any assets come out at all. `dotnet` + `Il2CppInspector` / `ilspycmd`
remain the type-model tools; `AssetRipper` is optional and its absence costs
nothing.

If the venv cannot be created (offline, no pip), the gate **pauses and asks the
user** rather than degrading silently, and only then may the subagent set
`RE Method: limited:unity-no-unitypy`. The wrappers still exit 3 with install
guidance when invoked directly (the path `test-unity-wrappers.sh` exercises).

## Legal

Extracted game art is copyrighted. Outside authorized use (own game, lawful
research), treat extracted assets as **reference only** and recreate in the same
style — do not ship them.

## Game mechanics & formulas (fidelity pass)

In the Phase 8 fidelity pass, deepen `$WORK/unity-digest.md` beyond the type
model + netcode to capture the playable rules:

- **Game mechanics** — core loop, win/lose conditions, level/wave progression,
  player/enemy state machines (from the C# `MonoBehaviour` methods).
- **Formulas** — damage/score/economy/cooldown calculations, drop rates, curve
  tables (constants and arithmetic in the decompiled C#).
- **Tunables** — `ScriptableObject` configs and serialized fields that balance
  the game.

Confidence: Unity **mono** is near-source (high); **il2cpp** gives signatures +
partial bodies (med). State the level reached.
