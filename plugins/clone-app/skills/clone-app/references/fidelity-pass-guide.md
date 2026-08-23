# Fidelity Pass Guide

The deep-extraction step (Phase 4). It runs **by default, before any gate** —
it learns about the target rather than committing to build anything, so there is
nothing for the user to approve. It produces a standalone report
(`fidelity-report-<date>.md`) alongside the feasibility report, and the build
spec assembled at Phase 9 references both.

## What it reuses

The fidelity pass does NOT re-download or re-decompile. It reads what Phase 2
already wrote to `$WORK/raw/decompiled` (sources, resources). It runs inside a Phase 4a
subagent so deep extraction never floods the orchestrator context.

## Steps (Phase 4 subagent)

1. **Full Tier-2 payloads.** Extend `$WORK/extracted/payloads.json` so EVERY first-party
   endpoint carries request/response/headers — not just auth/payment/core.
   Third-party endpoints stay Tier-1. This overrides the token-cost non-goal in
   `re-digest-contract.md`, which governs only the Phase 2 feasibility pass.
2. **In-app logic.** Run `extract-logic.py "$WORK/raw/decompiled" --out "$WORK/extracted/logic-signals.json"`,
   then distill `$WORK/extracted/logic-digest.md` per `logic-capture-guide.md`.
3. **Navigation graph.** Run `extract-nav-graph.py "$WORK/raw/decompiled" --out "$WORK/extracted/nav-graph.json"`.
4. **Backend recon.** Write `$WORK/extracted/backend-recon.md` from the contract per
   `backend-recon-guide.md` (confidence-stamped; a rebuild target, not stolen code).
5. **Unity (if applicable).** Deepen `$WORK/extracted/unity-digest.md` with game
   mechanics / formulas per `unity-re-guide.md`.

## Outputs

- `$WORK/extracted/logic-digest.md`, `$WORK/extracted/nav-graph.json`, `$WORK/extracted/backend-recon.md`
- deepened `$WORK/extracted/payloads.json`
- `$WORK/deliverables/fidelity-report-<date>.md` (standalone)
- the fidelity build spec (`clone-build-spec-template.md`, fidelity sections)

## Honest limits

Native Kotlin/Java and Unity-mono yield strong logic extraction; Unity-il2cpp is
medium; Flutter/React Native fall back to a `limited:` digest (Dart/JS are not in
the Java decompile). Backend server logic is never in the APK — `backend-recon.md`
infers a design, it does not recover server code.
