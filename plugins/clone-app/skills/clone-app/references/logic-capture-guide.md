# Logic Capture Guide

How the Phase 8 subagent turns `extract-logic.py`'s JSON signals (plus the
sources under `$WORK/raw/decompiled`) into `$WORK/extracted/logic-digest.md`.

## Input

`extract-logic.py "$WORK/raw/decompiled" --out "$WORK/extracted/logic-signals.json"` emits an
inventory: `viewmodels`, `usecases`, `validation`, `state_enums`,
`room_entities`, `room_daos`. Use it as the index of where logic lives; open the
named files to read the actual rules.

## `logic-digest.md` sections

```
# Logic Digest — <pkg>
## Workflows        per user flow (onboarding, core loop, payment): the step
                    sequence, the screen at each step, the trigger to advance
## Business rules   validation rules, computed values, formulas (from the
                    ViewModels / use-cases the signals point at)
## State model      state_enums + sealed classes → the states and transitions
## Local data       Room entities + DAOs → tables, columns, queries
## Confidence       per framework (see below)
```

## Framework-aware confidence

| Framework | Logic recoverable? | Confidence |
|---|---|---|
| Native Kotlin/Java (post R8 name recovery) | ViewModels, use-cases, validation read well | high |
| Jetpack Compose | logic in Kotlin, readable | high |
| Unity (mono) | C# near-source — mechanics + formulas | high–med |
| Unity (il2cpp) | type model + partial method bodies | med |
| Flutter / React Native | Dart/JS not in Java decompile | low — say so |

When confidence is low, record what little is recoverable (manifest, strings,
SDK list) and lean on screenshots + the API contract.
