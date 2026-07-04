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

`unity-assets.sh <apk> <out>` targets **AssetRipper**
(https://github.com/AssetRipper/AssetRipper). **Reality (verified, release 1.3.x
`AssetRipper.GUI.Free`):** AssetRipper is a **web-server GUI**, not a console
converter — there is no one-shot `<apk> -o <out>` mode and its web API has no
discoverable stable spec, so the wrapper does **not** fake a conversion:
- binary absent → exit 3 + install guidance (download the macOS arm64 release,
  export `ASSETRIPPER_CLI=<path>`; needs .NET);
- binary present → prints accurate GUI-run guidance and exits non-zero, **or**
  with `UNITY_ASSETS_MANUAL=1` writes a `manual-export-needed.md` marker and exits
  0 so the pipeline can defer asset extraction (run the GUI, load the APK,
  export). A programmatic headless driver is deferred until AssetRipper exposes a
  documented API.

For Unity games the **primary layout reference** is the Play screenshots in
`$WORK/screenshots/` (downloaded via `scrape-play-store.py`) plus
`design-tokens.json` from `res/` — Android `res/` carries only SDK chrome, since
the game art lives in AssetBundles. Treat any extracted assets as **reference
only** — do not ship them (copyright).

## Dependency gate (Phase 2a) vs graceful degradation

The Phase 2a Unity tool gate runs **before** the RE subagent: it detects
il2cpp/mono, checks `dotnet` / `Il2CppInspector` / `ilspycmd` / `AssetRipper`, and
**pauses to ask the user** (install vs proceed-limited) when a tool is missing —
so the cost of degradation is surfaced, not hidden. Only after the user consents
does the subagent write a partial `unity-digest.md` and set
`RE Method: limited:<reason>` (e.g. `limited:unity-no-dotnet`). The wrappers still
exit 3 with install guidance when invoked directly with a missing binary (this is
the path `test-unity-wrappers.sh` exercises).

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
