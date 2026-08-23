---
allowed-tools: Bash, Read, Glob, Grep, Write, Edit, Skill, Agent
description: Build a verified, prod-ready clone from a clone-build-spec.md (app or game)
user-invocable: true
argument-hint: <path to clone-build-spec.md or ./work/<pkg>>
argument: path to the build spec or work dir (optional)
---

# /clone-build

Drive the clone-build skill: spec → scaffold → gated task graph → verified code.

## Instructions

Follow the clone-build skill workflow in
`${CLAUDE_PLUGIN_ROOT}/skills/clone-build/SKILL.md` exactly, phases P0 through P5.

### Step 1: Locate the spec
If the user passed a path, use it. Otherwise look for
`./work/<pkg>/deliverables/clone-build-spec.md`. If none exists, tell the user to
run clone-app first — it writes the spec on every run.

### Step 2: Run the skill
Execute P0 → P5. Surface the plan's `gaps` and any `needs-human-input` tasks before
execution. Honor the Error Handling Summary table in SKILL.md.

### Step 3: Deliver
Ensure `./work/<pkg>/deliverables/build-report-<date>.md` is written and summarize
the outcome. For a game, work from `deliverables/reconstruction/` — it is the
real specification; the spec's screen list is a summary of it.
