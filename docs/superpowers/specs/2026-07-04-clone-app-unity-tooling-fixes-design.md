# clone-app Unity Tooling Fixes — Design

**Date:** 2026-07-04
**Status:** Approved-for-implementation
**Scope:** `plugins/clone-app/` Unity-handling scripts + SKILL.md Phase 2
**Trigger:** Empirical run of `/clone-app` on `com.loomgames.pixelflow` (Pixel Flow!,
Unity IL2CPP) surfaced three gaps in the Unity toolchain.

## Background

A full Phase 0–8 run against a real Unity IL2CPP game exposed that the Unity branch
of clone-app is the least-exercised path. Three concrete defects + one design gap
were found. This spec fixes them. No behavioral change to native-app analysis.

## Investigation findings (informed the fixes)

- **detect-unity.sh** works correctly on a full **XAPK** (it scans nested APKs and
  concatenates listings) — `il2cpp` was correctly detected for Pixel Flow. The bug
  only bites when a **single split APK** is passed (e.g. the base APK alone): the
  `libil2cpp.so` lives in `config.<abi>.apk`, the `global-metadata.dat` in the base
  APK, so the il2cpp check fails and the loose mono regex false-matches on
  `assets/bin/Data/Managed/Resources/*-resources.dat` resource stubs.
- **AssetRipper** (current release 1.3.14, `AssetRipper.GUI.Free`) is a **web-server
  GUI**, not a console converter. It exposes `--headless --port --log` but **no
  `<input> -o <out>` one-shot mode**. A live probe (`/swagger/index.html` returns
  200 but the OpenAPI spec JSON is not served at any standard path; no API paths
  are discoverable from `site.js`; informed `/api/*` guesses all 404) shows the web
  API is **not reliably scriptable blind**. The existing `unity-assets.sh`
  invocation `"$BIN" "$APK" -o "$OUT"` is therefore a silent no-op/error on the
  current build.
- **Il2CppInspectorRedux** (LukeFZ fork, 2026.2) ships a **framework-dependent**
  CLI (apphost targets .NET 10; ~2.3 MB) — it needs the .NET 10 runtime, which is
  not installed and is not mentioned anywhere in the skill.

## Changes

### Fix 1 — `detect-unity.sh`: tighten the mono regex

`grep -Eq 'assets/bin/Data/Managed/.*\.dll'` → `grep -Eq 'assets/bin/Data/Managed/[^/]+\.dll$'`.

- `[^/]+` requires the DLL to be a **direct child** of `Managed/` (where real
  managed assemblies like `Assembly-CSharp.dll` live), excluding the
  `Managed/Resources/` subdirectory.
- `$` anchors to end-of-line so `Foo.dll-resources.dat` resource stubs no longer
  match.
- il2cpp check is unchanged and still takes precedence. `test-detect-unity.sh`
  stays green (its `mono.apk` fixture is `assets/bin/Data/Managed/Assembly-CSharp.dll`,
  a direct child).

### Fix 2 — `unity-assets.sh`: honest capability contract

Replace the silent `"$BIN" "$APK" -o "$OUT"` with an accurate, graceful handler:

1. **Binary missing** → exit 3 + accurate guidance (unchanged contract; keeps
   `test-unity-wrappers.sh` green, which injects `ASSETRIPPER_CLI=/no/such/bin` and
   asserts exit 3 + "AssetRipper" text).
2. **Binary present** → it is the GUI.Free web-server build. The wrapper does **not**
   pretend to convert. It prints accurate guidance (open the GUI, load the APK,
   export) and exits non-zero **unless** `UNITY_ASSETS_MANUAL=1` is set, in which
   case it records a `manual-export-needed` marker in `$OUT` and exits 0 so the
   pipeline can continue (assets become a deferred, manual step).

This removes the false claim of one-shot conversion. A real headless driver is
deferred (requires AssetRipper to expose a documented, stable API — currently absent).

### Fix 3 — SKILL.md Phase 2: explicit Unity **dependency gate**

Add a Phase 2 pre-check that runs **before** dispatching the RE subagent, only when
`detect-unity.sh` reports `il2cpp` or `mono`:

1. Classify the build (il2cpp/mono) — already done by `detect-unity.sh`.
2. Check tool availability:
   - il2cpp → needs `Il2CppInspector` (or `$IL2CPP_INSPECTOR_CLI`) **+ .NET 10 runtime** (`dotnet --version`).
   - mono → needs `ilspycmd` **+ .NET runtime**.
   - both → needs `AssetRipper` (or `$ASSETRIPPER_CLI`).
3. If a tool is missing → **pause and tell the user** the *cost of degradation* in
   concrete terms ("IL2CPP type model will be empty — game logic is unrecoverable
   either way, but class/method names will be missing too"), give the exact install
   commands with size/time, and ask: install now, or proceed limited? Only proceed
   to `limited:` after the user acknowledges.
4. Surface the install commands in the skill itself (currently absent):
   - `brew install --cask dotnet-sdk` (.NET 10, sudo — user-run).
   - Il2CppInspectorRedux release download (self-contained? No — framework-dependent,
     needs the SDK above) + put on PATH or `IL2CPP_INSPECTOR_CLI`.
   - `brew install ilspycmd` (mono).
   - AssetRipper release download + `ASSETRIPPER_CLI`.

This replaces today's silent `limited:` degradation with a **visible, consented
gate** — the "best-practice" answer to the author's question.

### Fix 4 — `unity-re-guide.md`: accurate tooling reality

Update the tool section to: (a) state AssetRipper Free is GUI/web-server (no
one-shot CLI), (b) state Il2CppInspectorRedux is framework-dependent on .NET 10,
(c) list install commands, (d) document the `UNITY_ASSETS_MANUAL=1` escape hatch +
the consented-degradation contract from Fix 3.

## Out of scope

- A real AssetRipper headless driver (blocked on a documented API; revisit if
  AssetRipper exposes one).
- Switching to UnityPy for asset extraction (would require pip — violates the
  repo's stdlib-only rule for shipped scripts).
- Releasing a new plugin version (`0.2.0`) / bumping the installed cache — the fix
  lands in the repo working copy; re-install picks it up.

## Test plan

1. `bash plugins/clone-app/tests/test-detect-unity.sh` — green (regex change).
2. `bash plugins/clone-app/tests/test-unity-wrappers.sh` — green (exit-3 contract).
3. `bash plugins/clone-app/tests/test-skill-phases.sh` — green (Phase 2 edit adds,
   doesn't remove, required strings).
4. `bash plugins/clone-app/tests/smoke-structure.sh` — green (6 Unity scripts still
   present + executable).
5. `bash plugins/clone-app/tests/run-all.sh` — full suite green.
6. Manual: re-run the il2cpp detection on Pixel Flow's base-only APK → now reports
   `il2cpp` (not `mono`).

## Deliverables

- `plugins/clone-app/skills/clone-app/scripts/detect-unity.sh` (Fix 1)
- `plugins/clone-app/skills/clone-app/scripts/unity-assets.sh` (Fix 2)
- `plugins/clone-app/skills/clone-app/SKILL.md` Phase 2 (Fix 3)
- `plugins/clone-app/skills/clone-app/references/unity-re-guide.md` (Fix 4)
- This design note.
