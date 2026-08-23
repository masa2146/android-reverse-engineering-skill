# clone-build

The build/verify stage of the **discover → analyze → build** pipeline
(`market-research → clone-app → clone-build`). Takes the `clone-build-spec.md` and
`$WORK/` artifacts produced by clone-app (Phase 9) and drives them to running,
verified, production-ready code.

## How it works

A shared 6-phase spine (`skills/clone-build/SKILL.md`) plus two on-demand branch
guides:

- **app** branch — Flutter / native Android / React Native. Build + install + launch
  hard gate always; `adb screencap` visual-diff when an emulator is present.
- **game** branch — Unity, driven live via the MCP-for-Unity tools (scaffold via
  Unity CLI, build/screenshot/test gates).

Robustness is structural: `gen-build-plan.py` emits a deterministic task graph where
every task carries a machine-checkable gate (`build` / `tdd` / `visual-diff` /
`launch-crash`), run through `run-gate.sh`. A task is `done` only when its gate
exits 0 — the model never self-certifies. Execution uses
`superpowers:subagent-driven-development` (fresh subagent + reviewer per task).

## Scripts
- `detect-branch.sh` — spec → `game|app` + substack.
- `preflight.sh` — probe Unity / flutter / gradle / node / adb → JSON.
- `gen-build-plan.py` — spec + artifacts → `build-plan.json` (deterministic).
- `run-gate.sh` — single gate-execution chokepoint.

## Tests
```bash
bash plugins/clone-build/tests/run-all.sh
```
Offline fixtures only — no live Unity / emulator / network.

## Status
Branch-agnostic core. The app branch, game branch, and clone-app Phase-7 wiring land
in later plans.
