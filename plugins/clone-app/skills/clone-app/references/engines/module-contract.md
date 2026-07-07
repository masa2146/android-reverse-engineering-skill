# Engine Module Contract

Every per-engine extraction module (unity-il2cpp, unity-mono, unreal, godot,
native) is loaded on demand by `detect-engine.sh` + the Phase 2 dispatcher and
MUST write these four artifacts to `$WORK/`, so the Phase 8 Clone Build Spec
assembler never branches on engine.

## Outputs

1. **`mechanics-digest.md`** — recovered logic / rules / formulas + data-layer
   values (balance tables, curves, drop rates). Every entry carries a confidence
   stamp:
   - `observed` — from near-source (mono/GDScript/Blueprint).
   - `inferred` — from extracted data (ScriptableObjects, DataTables).
   - `signature-only` — il2cpp type model; method body not recovered.
   - `not-recoverable` — native C++ / stripped; flagged, not guessed.
2. **`game-assets/` + `manifest.json`** — extracted textures/sprites/audio/
   meshes/scenes/prefabs/fonts. `manifest.json` records per-type counts and the
   coverage shape consumed by `gen-coverage-report.py`:
   `{"engine", "assets": {"expected", "extracted", "by_type"}, "mechanics", "notes"}`.
   `expected` = archive entry count found in the package; `extracted` = files
   actually written. Never claim more than was written.
3. **`netcode-recon.md`** — observed netcode/backend surface (Photon/PlayFab/
   Mirror/HTTP), same confidence stamps. Complements `backend-recon.md`.
4. **`coverage-report.md`** — produced by
   `gen-coverage-report.py manifest.json --out coverage-report.md`; the honest
   covered/partial/missing rollup. Downstream reads this to avoid mistaking
   partial extraction for complete.

## Decision gates (dispatcher-owned, not module-owned)

- **Dependency gate** — if a module's tool/venv is missing, PAUSE and surface the
  install cost + a `limited:` proceed option. Never degrade silently.
- **Layer-2 escalation** — expensive native disassembly (e.g. il2cpp via Ghidra)
  is offered only when Layer-1 leaves a gap, and only on user consent.

## Legal stance

Extracted assets are copyrighted and recorded **reference only** — recreate in
the same style. This pipeline targets faithful rebuild, not a 1:1 copy.
