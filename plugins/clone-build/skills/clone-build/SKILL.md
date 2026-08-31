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

### Where the code goes

Reports go to `$WORK/deliverables/`. **Code goes to `$REPO`** — never into
`extracted/` or `raw/`.

```bash
REPO="${CLONE_BUILD_REPO:-$WORK/clone}"
```

- **Default `$WORK/clone/`** — fine for a throwaway or a first pass.
- **A separate top-level repo is better for real work**, and is what you should
  prefer once the clone is a product rather than an experiment:
  - `$WORK` is often several GB of extraction plus `raw/`; a product repo does not
    belong nested inside it.
  - `clean-workdir.sh` deletes `raw/`. A repo living under `$WORK` is one careless
    cleanup away from being collateral.
  - The clone has its own git history, CI and lifecycle, independent of the
    analysis that seeded it.

Ask the user for `$REPO` when it is not set and the target looks like real work.
Record the chosen path in the build report so a later session finds it.

**`$WORK` is read-only from the build's point of view** apart from
`deliverables/`. The extraction is reference material: reference it by absolute
path, do not copy `game-assets/` into the repo.

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
`$REPO`. If `$REPO` already holds a project (a resumed build, or a repo the user
started by hand), **do not scaffold over it** — verify it builds, then continue
from P1b. For `game`, this is a headless Unity CLI `-createProject` plus the
MCP-for-Unity package, then a connection check. For `app`, `flutter create` / a
gradle template / `react-native init`. Missing prerequisites → print exact setup
guidance and pause; never half-fail.

### P1b: Install the bootstrap

clone-app's Phase 2g wrote the clone project's day-one instructions. Copy them in
before any code is generated — an agent told nothing about the extraction invents
assets, and that is the most expensive failure in this pipeline.

```bash
BS="$WORK/deliverables/bootstrap"
REPO="${CLONE_BUILD_REPO:-$WORK/clone}"
# never clobber a CLAUDE.md the project already owns — merge by hand instead
[ -f "$BS/CLAUDE.md" ] && [ ! -f "$REPO/CLAUDE.md" ] && cp "$BS/CLAUDE.md" "$REPO/CLAUDE.md"
mkdir -p "$REPO/Docs/assets"
cp "$WORK"/extracted/asset-guide/*        "$REPO/Docs/assets/"  2>/dev/null
cp "$WORK"/extracted/REFERENCE-SOURCES.md "$REPO/Docs/"         2>/dev/null
cp "$WORK"/deliverables/clone-build-spec.md "$REPO/Docs/"       2>/dev/null
[ -d "$WORK/deliverables/reconstruction" ] && cp -R "$WORK/deliverables/reconstruction" "$REPO/Docs/"
```

If `$BS/CLAUDE.md` is absent the working dir predates Phase 2g — generate it now:

```bash
python3 <clone-app>/skills/clone-app/scripts/gen-project-bootstrap.py "$WORK" \
  --out "$WORK/deliverables/bootstrap" --project-name "<CloneName>"
```

Same for the asset guide, if `extracted/asset-guide/` is missing: run clone-app's
`gen-asset-guide.py`, `gen-ui-map.py` and `gen-reference-sources.py` against
`$WORK/extracted`. All are deterministic and take seconds.

**Never hand-write a hand-off prompt for the build session.** The bootstrap is
that prompt, and it is generated from measurements rather than memory.

**Do not copy `extracted/game-assets/` into the repo.** It is reference material,
hundreds of MB, and not yours to ship. Reference it through `$W` as the bootstrap
`CLAUDE.md` does. Art enters the repo only through the import step, recreated or
imported deliberately — see `unity-import/ImportExtracted.cs`, which rebuilds each
entity **from its node tree** (hierarchy, local transforms, per-slot materials,
fracture debris under a disabled root).

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

**The two branches produce different spines, not different labels.**

*App*: `design-system` → one `ui` task per nav-graph node → one `api` task per
endpoint → `logic` → `integration`.

*Game*: nav-graph nodes are `*View` **type names** with no screenshot to diff
against, and the endpoint list describes a backend a local rebuild stubs — so a
game plan is not built from them. It is built from what a game actually needs:

| type | source | gate |
|---|---|---|
| `engine-settings` | `game-assets/project-settings/`, `physics.json` | build — measured settings applied **before** gameplay code |
| `art-import` | `asset-guide/ASSET-INDEX.tsv`, grouped by archetype | build — prefabs built **from `entity.json` → `nodes`** (hierarchy, local TRS, per-slot materials, debris under a disabled root) |
| `mechanic` | the chapter headings of `reconstruction/02-GAMEPLAY-MECHANICS.md` | tdd |
| `level-pipeline` | schema · editor + image importer · loader with mid-level save | tdd — a board round-trips unchanged |
| `scene` | the **real canvas dump** `game-assets/ui/*.json`, largest first | visual-diff |
| `tuning` | the sections of `reconstruction/05-UNKNOWNS.md` | manual — run the experiment or defer explicitly, never invent |

Game `gaps` are judged on game inputs: missing `game-assets/`, `asset-guide/` or
`reconstruction/`. It does **not** demand `design-tokens.json` (for a Unity title
that file is SDK noise) or store screenshots.

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
