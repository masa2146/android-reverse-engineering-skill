---
allowed-tools: Bash, Read, Glob, Grep, Write, Edit, WebFetch, WebSearch, Skill, Agent
description: Extract everything from a Google Play app — content, API surface, mechanics, architecture, build spec — then judge cloning it
user-invocable: true
argument-hint: <Google Play URL or package name>
argument: Google Play URL or package name (optional)
---

# /clone-app

Take a Google Play app apart completely, then assess cloning it.

## Instructions

Follow `${CLAUDE_PLUGIN_ROOT}/skills/clone-app/SKILL.md` exactly, phases 0
through 9.

### Step 1: Get the target
If the user passed a URL or package name as an argument, use it. Otherwise ask
for the Google Play URL or package name.

### Step 2: Run the skill

**Everything that learns about the target runs by default.** Do not offer the
extraction, the API surface, the deep pass or the reconstruction as options and
do not wait to be asked for them — by the end of Phase 5 the target is fully
extracted and written up.

Phases 0–5 (no interaction):
- **0–1** working directory + package download
- **2** reverse engineering, engine dispatch, **full content extraction**
  (assets grouped per entity, levels, physics, shaders, particles, animations,
  fonts, UI, project settings) and the **IL2CPP API surface**
- **3** store metrics and screenshots
- **4** deep extraction: full API payloads, in-app logic, navigation graph,
  backend recon
- **5** for a game: the **reconstruction** — architecture, mechanics, runtime
  flow, meta/LiveOps design, unknowns ledger, code skeleton

Phases 6–9 finish the paperwork: stack choice, effort and cost, reports, build
spec.

**Exactly one interaction point:** Phase 6, which clone stack to cost the
estimate against. There is no other gate — nothing later is expensive enough to
be worth asking about.

The **implementation plan is not written here.** It belongs to the session that
builds: that one has the repo open and a free context. Finish by pointing the
user at the working directory and telling them to run `writing-plans` in a fresh
session with `deliverables/clone-build-spec.md`.

Skip Phases 4 and 5 **only** if the user explicitly asks for a fast,
report-only pass, and say so in the report.

Honor the Error Handling Summary table in SKILL.md at every phase.

### Step 3: Deliver
Point the user at `./work/<package>/` and its `README.md`, which maps the three
layers:
- `deliverables/` — `clone-report-<date>.md`, `fidelity-report-<date>.md`, and
  for a game `reconstruction/`
- `extracted/` — `game-assets/`, `api-surface.*`, RE digests, `store/`
- `raw/` — package, decompiled sources, unpack scratch (regenerable; clear it
  with `clean-workdir.sh` when finished)

Summarise the verdict, and for a game say plainly what was recovered (design,
mechanics, assets, constants) and what was not (script field values, shader
bytecode, method bodies).
