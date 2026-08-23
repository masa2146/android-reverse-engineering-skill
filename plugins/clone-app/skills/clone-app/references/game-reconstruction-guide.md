# Game Reconstruction Guide (Phase 9)

How to turn the extracted artifacts into a **buildable reconstruction** of a
game: its architecture, every mechanic, the stage-by-stage runtime flow, the
meta and LiveOps design, an honest list of what could not be recovered, and a
code skeleton that compiles.

This is the deepest output the skill produces. Phases 0–8 collect facts; this
phase turns them into something a developer can build from.

## Inputs — and how to read them without destroying your context

| Artifact | Size on a real game | How to use it |
|---|---|---|
| `$WORK/api-surface.json` / `.md` | **4–10 MB** | **NEVER read whole.** Query it (recipes below). |
| `$WORK/game-assets/manifest.json` | small | read fully |
| `$WORK/game-assets/entities/_index.json` | medium | read fully or filter |
| `$WORK/game-assets/levels/level-analysis.json` | small–medium | read fully |
| `$WORK/game-assets/physics.json`, `project-settings/README.md` | small | read fully |
| `$WORK/game-assets/scenes/*.tree.txt` | 40 KB+ each | grep for canvases/managers, or read one |
| `$WORK/game-assets/ARCHITECTURE.md` | medium | read fully |
| `$WORK/game-assets/shaders/README.md`, `IMPORT.md` | small | read fully |
| `$WORK/re-digest.md`, `payloads.json` | small | read fully |
| audio / particles / animator listings | — | `ls` them, do not read the JSON |

### Query recipes (use these, they are what worked)

```bash
# every class in the game assemblies, with fields and methods
python3 - <<'PY'
import json
d = json.load(open("$WORK/api-surface.json"))["assemblies"]
core = d.get("Core.dll") or d.get("Assembly-CSharp.dll") or {}
for name in sorted(core):
    e = core[name]
    print(f"### {name}\n  F: {', '.join(e['fields'][:34])}\n  M: {', '.join(e['methods'][:34])}")
PY

# one subsystem at a time — this is the main working loop
python3 - <<'PY'
import json
c = json.load(open("$WORK/api-surface.json"))["assemblies"]["Core.dll"]
for n in ["Core.BallController", "Core.LevelController", "Core.Obstacle"]:
    e = c.get(n)
    if e: print(n, "\n F:", e["fields"], "\n M:", e["methods"], "\n P:", e["properties"], "\n")
PY

# which assemblies exist and how big each is
python3 -c "
import json;d=json.load(open('$WORK/api-surface.json'))['assemblies']
print(sorted(((len(v),k) for k,v in d.items()), reverse=True)[:15])"
```

Work **subsystem by subsystem**: dump 10–20 related classes, write that section,
move on. Never hold the whole surface in context.

### Finding the game's own assemblies

Ignore `Unity*`, `System*`, `mscorlib`, `netstandard`, `Mono*`, `TextMesh*` and
the studio's framework assemblies unless a mechanic lives there. What remains —
typically `Assembly-CSharp` plus a small number of studio-named DLLs — is the
game. Rank by type count; the biggest non-engine assembly is almost always the
game core.

## Evidence tags — mandatory on every claim

| Tag | Meaning |
|---|---|
| **[D]** | **Data** — read from extracted assets: level JSON, prefab component values, physics constants, project settings, asset names. Exact. |
| **[S]** | **Signature** — from the IL2CPP metadata. The class really has this field / this method. Structure certain; the field's **value** and the method's **body** are not in the package. |
| **[I]** | **Inferred** — deduced by combining [D] and [S]. Must read as an inference. |
| **[X]** | **Not recoverable** — goes in `05-UNKNOWNS.md`. |

An untagged claim is a bug. **Never state a number you did not measure.** If a
formula is unknown, say so and put it in `05-UNKNOWNS.md` — do not invent a
plausible one and present it as recovered.

## Output structure

```
$WORK/reconstruction/
  README.md                  index + evidence legend + the hard limit
  01-ARCHITECTURE.md         services, scenes, data flow, persistence, analytics
  02-GAMEPLAY-MECHANICS.md   core loop, every element, win/lose resolution
  03-FLOW.md                 stage-by-stage: which animation/VFX/sound fires when
  04-META-LIVEOPS.md         economy, progression, monetisation, events, ads
  05-UNKNOWNS.md             what is missing, why, and how to determine it
  code/                      engine-native skeleton (see below)
```

### README.md
Index table, the evidence legend above, a Sources list with real counts pulled
from the artifacts, and a closing paragraph naming **the hard limit**: method
bodies are AOT-compiled and MonoBehaviour/ScriptableObject field values are
stripped, so mechanisms are recovered and numbers are not.

### 01-ARCHITECTURE.md
- Engine, build type, game assemblies with type counts **[D/S]**
- The studio's own framework, if any — say so early; it changes how a clone
  should be structured
- **Service inventory**: one table row per service class, with its
  responsibility read off its method names **[S]**
- Any **orchestrator** (a sequence/queue/state-machine service that decides what
  the player sees next). Find it — most live-service games have one, and missing
  it produces a clone where every popup fights for the screen.
- Scenes and their contents **[D]** from `scenes/*.tree.txt`
- UI ownership: the controller that holds screen references, its show methods,
  which screens are Addressable/lazy **[S/D]**
- Data flow, end to end, as a code block
- Persistence: every save key named in the metadata **[S]**
- Remote content pipeline, if present
- Analytics: the typed event classes **[S]**

### 02-GAMEPLAY-MECHANICS.md
The longest document. For **each** gameplay system:
1. Name the class, then list its real fields and methods **[S]**
2. Explain the mechanic those names describe
3. Give the call order as a code block where the method names imply one
4. Call out the design details that make the game feel the way it does
5. Tag every number: measured **[D]** or unknown **[X]**

Cover at minimum: player input and control; the projectile/avatar and its
physics; the object/enemy base class and its mass, damage and destruction model;
**every special element** one section each; win/lose resolution including any
settle/idle gate; camera; adaptive performance; the level data format with real
statistics from `level-analysis.json` **[D]**; difficulty tiers and their
presentation.

Include the **element introduction curve** from `level-analysis.json` as a table
— it is the clone's content roadmap. Note elements present in code but absent
from shipped levels; they are usually remote/event content **[I]**.

### 03-FLOW.md
Stage by stage, with **asset names from the extraction** attached to each beat:
cold start · main menu · starting a level · a single player action · the impact
/ resolution chain · win · lose · out-of-resource · abilities-in-play ·
notifications.

For each stage give an indented call-chain code block, and against each beat
name the concrete animator controller, particle system, audio clip and UI canvas
**[D]** — pull them from `animations/controllers/`, `particles/`, `audio/`,
`ui/` and `scenes/*.tree.txt`. This is the document that answers "what shows up
when", so a beat without its assets named is an incomplete beat.

### 04-META-LIVEOPS.md
Economy (currencies, reward plumbing, transaction contexts), the resource/energy
system, abilities and their inventory, shop and IAP (read `ShopManifestEntry`-
equivalent fields as a design spec), each live event with its config/service/
state triple, ads, retention features, social.

For each event, state its **shape** — how it starts, what earns progress, what
it pays out, how it ends — from the method names **[S]**. Call out reusable
design patterns explicitly; that is the transferable value.

### 05-UNKNOWNS.md
Exactly three categories:
1. **Field values** — a table: unknown · where it lives · how to determine it.
   Mark anything partially recoverable from data and say how.
2. **Shader source** — note what *is* recovered (the interface) and split the
   shaders into drop-in / buy / re-author from `shaders/README.md`.
3. **Method bodies** — name the specific algorithms affected.

End with the practical read: design recovered, balance not, and balance is the
cheaper half.

### code/
An engine-native skeleton mirroring the original's class layout and naming so it
can be read next to `api-surface.md`.

Rules:
- Every class, field and method must exist in the original **[S]**; anything you
  add is prefixed `// addition:`.
- Every unknown constant gets `// TODO tune` and a sensible starting value.
- Every measured constant gets `// [D]` and the measured value.
- Include the measured project settings in `code/README.md` as a table — gravity,
  fixed timestep, solver iterations, physic materials — so a clone starts with
  the original's feel instead of Unity defaults.
- Write the **core loop only**: data format, level control, player control,
  the object base class, the special elements, abilities, the resource service.
  Meta and LiveOps are specified in `04`; they are ordinary service code.
- It must be syntactically valid and self-consistent. Provide thin stand-ins for
  the framework services it calls, clearly marked as additions.

## Working order

1. Read `manifest.json`, `IMPORT.md`, `coverage-report.md`, `level-analysis.json`,
   `physics.json`, `project-settings/README.md`, `ARCHITECTURE.md`. Small files,
   all of them.
2. List the game assemblies and rank by type count.
3. Subsystem loop: query 10–20 classes → write that section → next.
4. `ls` the animator/particle/audio/ui listings and attach them in `03-FLOW.md`.
5. Write `05-UNKNOWNS.md` last, from the `// TODO tune` markers you accumulated.
6. Write the code skeleton against the sections you wrote.

## Determinism

The **inputs** are deterministic: rerunning the extraction on the same package
produces a byte-identical tree, and the metadata dump is byte-identical too.
The **documents** are authored, so wording varies between runs. What must not
vary: the file set, the section structure, the evidence tags, and every factual
claim — those come from the artifacts, not from judgement. If two runs disagree
on a fact, one of them read the artifacts wrong.

## Honesty rules

- Only three things are genuinely unrecoverable (field values, shader bytecode,
  method bodies). Any other "not recoverable" claim is a tooling gap to report,
  not a limitation to assert.
- Never present an inferred number as measured.
- If a subsystem could not be covered, say so in `README.md` rather than leaving
  a gap the reader has to notice.

## Legal

Extracted art is reference material. The transferable output is the structure —
architecture, mechanics, schema, physics constants, taxonomy. Say this in
`README.md` and do not soften it.
