---
description: Turn a clone-build-spec.md plus its $WORK/ artifacts into running, verified, production-ready code — for apps (Flutter / native Android / RN) or games (Unity via MCP). Drives a deterministic task graph where every task is gated by a machine-checkable build / TDD / visual-diff / launch check, so even a weak model in a fresh session converges on a correct clone. Use after clone-app has produced a build spec (its Phase 9) — clone-app now writes one on every run. 中文触发词：克隆构建、生成可运行代码、构建克隆
trigger: build the clone|clone build|generate the app from spec|build from clone-build-spec|implement the clone|克隆构建|生成可运行代码
---

# Clone Build — Spec to Prod-Ready Code

Take `clone-build-spec.md` and the `$WORK/` artifacts from clone-app (Phase 9), scaffold
a buildable project, generate a gated task graph, and drive it to verified,
production-ready code. Games go through the Unity-MCP branch; apps through the
Flutter / native-Android / RN branch. The two branches share this spine; their
specifics live in `references/{game,app}-build-guide.md`, loaded on demand.

This skill orchestrates 6 phases (P0–P5). Deterministic steps are factored into
helper scripts under `${CLAUDE_PLUGIN_ROOT}/skills/clone-build/scripts/`.

## Legal note
Only build clones you are authorized to (your own apps, lawful interoperability /
research). The clone-app legal note still governs which apps may be analyzed at all.
Extracted game art is reference-only outside authorized use — recreate in-style.

## P0: Preflight & spec load
Locate the build spec (default `./work/<pkg>/deliverables/clone-build-spec.md`)
and its `$WORK` artifact dir. clone-app lays the working dir out in three layers:
- `deliverables/` — the spec, the feasibility and fidelity reports, and for a
  game `reconstruction/` (architecture, mechanics, runtime flow, unknowns, code
  skeleton). **For a game, `reconstruction/` is the real specification** — read
  it before the spec's screen list.
- `extracted/` — `game-assets/` (per-entity models, textures, levels, physics,
  shaders, particles, animations, fonts, UI, project settings), `api-surface.*`,
  RE digests, `store/`.
- `raw/` — package and decompiled sources; regenerable, may already be deleted.

An older flat working dir can be converted with clone-app's
`migrate-workdir.sh`. If the spec is missing, stop and tell the user to run
clone-app first.

Write build output into `$WORK/deliverables/` (reports) and `$WORK/clone/` (code)
— never into `extracted/` or `raw/`.

Detect the branch:
```bash
read BRANCH SUBSTACK < <(bash ${CLAUDE_PLUGIN_ROOT}/skills/clone-build/scripts/detect-branch.sh "$SPEC")
```
Probe the toolchain:
```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/clone-build/scripts/preflight.sh --out "$WORK/deliverables/preflight.json"
```
Then load **only** the matching branch guide: `references/app-build-guide.md` for
`app`, `references/game-build-guide.md` for `game`. (These are added in later plans;
if absent, note the gap and continue with the spine.)

## P1: Project scaffold
Per the loaded branch guide, scaffold an empty **buildable** project into
`$WORK/clone/`. For `game`, this is a headless Unity CLI `-createProject` plus the
MCP-for-Unity package, then a connection check. For `app`, `flutter create` / a
gradle template / `react-native init`. Missing prerequisites → print exact setup
guidance and pause; never half-fail.

## P2: Plan generation
Generate the gated task graph from the spec + artifacts:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/clone-build/scripts/gen-build-plan.py \
  "$SPEC" --work "$WORK" --out "$WORK/deliverables/build-plan.json"
```
The schema and the generation rules are in `references/plan-contract.md`; the gate
kind per task type is in `references/gate-catalog.md`. Any entry in the plan's
`gaps` array, or any task with status `needs-human-input`, is surfaced to the user
before execution — the build never silently fills a hole.

## P3: Execution loop
Execute the plan task-by-task using **superpowers:subagent-driven-development**: a
fresh subagent per task implements it, then runs its gate through
`${CLAUDE_PLUGIN_ROOT}/skills/clone-build/scripts/run-gate.sh --kind <kind>
--command "<cmd>"`. The forcing rule (see `plan-contract.md`) holds: a task is
`done` only when `run-gate.sh` printed `RESULT: PASS`. A reviewer subagent re-checks
the gate evidence before dependents unblock. Per-task status is written back to
`build-plan.json`, so a dropped session resumes by skipping done-and-gated tasks.
If subagent-driven-development is unavailable, run tasks inline but still gate each
through `run-gate.sh`.

## P4: Integration verify
Run the `integration` task: full build, launch, and an end-to-end walk of every
screen/flow, confirming no crash and that navigation matches `nav-graph.json`. For
the app branch this is the always-on hard gate (build + install + launch + no fatal
log); the visual pass runs when an emulator/device is present, else it is SKIP.

## P5: Build report
Write `$WORK/deliverables/build-report-<YYYY-MM-DD>.md` from
`references/build-report-template.md`: tasks done, gate evidence, visual-fidelity
verdicts (or SKIP + reason), remaining `needs-human-input` items, and next manual
steps.

## Error Handling Summary
| Scenario | Action |
|---|---|
| Spec / artifacts missing | stop; tell user to run clone-app first (it writes the spec on every run) |
| Branch guide file absent | note the gap, continue with the spine |
| Toolchain missing (Unity / flutter / gradle / node) | print setup guidance, pause |
| MCP not connected after Unity scaffold | guidance, poll editor state, pause |
| Gate fails | task stays open; subagent retries; after N retries escalate with evidence |
| Visual-diff below threshold | iterate up to N, then flag for user review; never force-pass |
| Emulator absent (app) | hard gate still runs; visual = SKIP + guidance |
| subagent-driven-development unavailable | run tasks inline, still gate via run-gate.sh |
| Mid-run session death | resume from build-plan.json status — skip done-and-gated tasks |
