# PROMPT — clone-app: full, grouped, ready-to-use Unity asset extraction

> Bunu yeni bir Claude Code oturumunda `/Users/fatih.bulut/PythonWorks/clone_app_skill`
> dizininde çalıştır. Prompt İngilizce, çünkü repo İngilizce ve ajanın ürettiği kod /
> doküman repo diliyle tutarlı olmalı.

---

Read `CLAUDE.md` first — it is binding. Then implement the upgrade below.

## 0. Mission

Today `/clone-app` produces a *feasibility report* but **extracts no game content**.
Upgrade it so that, for a Unity game, one automated pass extracts **everything the
package contains** — meshes, textures, sprites, materials, animations, audio, fonts,
levels, scenes, prefab structure, physics tuning — and writes it out **grouped by the
thing it belongs to** and **directly importable**, not as a flat dump of anonymous files.

The success test is a human one: after the run, someone opens
`work/<pkg>/game-assets/entities/JamJarOrange_3/` and finds — in that one folder — the
model, its broken pieces, its textures, its material values, its collider/rigidbody
numbers, a preview image, and a one-file description. Nothing else needs to be hunted for.

## 1. Hard constraints (from CLAUDE.md — do not violate)

- **Never modify `plugins/android-reverse-engineering/`.** `git status --porcelain plugins/android-reverse-engineering/` must print nothing before you commit.
- Shipped core scripts + all tests are **stdlib-only Python** and `#!/usr/bin/env bash`. Heavy deps (UnityPy, numpy, Pillow) go **only** into the opt-in venv created by `scripts/setup-extraction-venv.sh` and declared in `scripts/requirements-extraction.txt`.
- Working dir is always `./work/<package>/` relative to the user's cwd, never inside the plugin.
- Bash tests use `set -uo pipefail` (not `-e`) and aggregate failures into a `fail` var so every assertion runs.
- Python tests run **offline against `tests/fixtures/`** — never hit the network, never require a real APK.
- Conventional Commits scoped to the plugin: `feat(clone-app): …`, `test(clone-app): …`.
- Keep the scripts-for-deterministic / rubrics-for-judgment split. New deterministic work = a script. New judgment work = a reference doc.

## 2. Current state — verified, not assumed

Read these before changing anything:

- `plugins/clone-app/skills/clone-app/SKILL.md` — Phase 2b engine dispatch, Phase 2c Unity tool gate, Phase 2d subagent.
- `plugins/clone-app/skills/clone-app/scripts/unity-assets.sh`
- `plugins/clone-app/skills/clone-app/references/unity-re-guide.md`
- `plugins/clone-app/skills/clone-app/references/engines/module-contract.md`
- `plugins/clone-app/skills/clone-app/scripts/gen-coverage-report.py`
- `plugins/clone-app/tests/test-unity-wrappers.sh`

**The gap:** `unity-assets.sh` never extracts anything. It targets AssetRipper, whose
current release is a web-server GUI with no one-shot CLI, so the wrapper honestly
refuses: exit 3 (binary absent), exit 4 (present but undrivable), or with
`UNITY_ASSETS_MANUAL=1` it writes `manual-export-needed.md` and exits 0. Consequently
`game-assets/` is empty or a stub for every Unity run, `manifest.json` is never
populated with real content, and `coverage-report.md` reports on nothing.

Meanwhile `requirements-extraction.txt` already declares `UnityPy>=1.20` and
`setup-extraction-venv.sh` already builds the venv — **the scaffolding exists and no
script uses it.** That is the hole to fill.

## 3. Proven technique — this is the playbook, not a research task

A full manual extraction of `com.cyphergames.royalsmash` (Unity 6000.0.62f1, IL2CPP,
341 MB XAPK) was completed with UnityPy in ~4 minutes of compute. Everything below is
**verified working**, including the failure modes. Implement against these facts; do
not rediscover them.

### 3.1 Package unpacking

- An XAPK is a zip of APKs. Unzip it, then unzip each inner APK. Unity payload lives at `assets/bin/Data/` in the **base APK** and, when Play Asset Delivery is used, in a separate `UnityDataAssetPack.apk` (that is where the bulk of the content is — 189 MB of 341 MB in the reference app). Native libs (`libil2cpp.so`) live in `config.<abi>.apk`.
- **Serialized files are split.** `sharedassets0.assets.split0 … .split60`, `level1.split0…`. You must concatenate `<name>.splitN` in numeric order into `<name>` before loading, or you get nothing. Merge every source tree (base + asset packs) into one flat directory (hardlink the non-split files, concatenate the split groups) and load that directory.
- Unity version string is readable from the head of `globalgamemanagers`. `boot.config` carries build GUID and gfx settings.
- `assets/bin/Data/ScriptingAssemblies.json` lists every managed assembly — this is the cheapest, highest-signal SDK/tech inventory in the whole package (it revealed SignalR, MessagePack, MongoDB.Bson, Jint, Firebase set, AppLovin MAX, Spine, Odin, Sentry in the reference app). Always capture it.

### 3.2 Loading

`UnityPy.load("<merged-dir>")` on the **whole merged directory at once** — not per file.
Cross-file `PPtr` references (Sprite→Texture2D, MeshFilter→Mesh, Renderer→Material→Texture)
only resolve when every file is in one environment. On the reference app this loaded
34 237 objects in ~3 seconds.

### 3.3 Recoverability matrix — VERIFIED, and the governing rule

**The rule that explains everything: if it is a Unity *engine* type, its type tree ships
in the file and every field is readable. Only *user* types (MonoBehaviour /
ScriptableObject) have their type trees stripped in an IL2CPP release build.**

An earlier pass under-reported this badly — several things were called "unrecoverable"
when they were merely *not exported yet*. Do not repeat that mistake. Each row below was
executed against the reference package.

**Genuinely NOT recoverable (only three things):**

| Data | Why |
|---|---|
| **MonoBehaviour / ScriptableObject custom fields** | type trees stripped. `read_typetree()` raises `ValueError: Expected to read N bytes, but only read M bytes`. Only base fields (`m_GameObject`, `m_Enabled`, `m_Script`, `m_Name`) reachable. Handle, do not crash. This is what costs you the balance tables, booster parameters and LiveOps configs. |
| **Shader HLSL / compiled bytecode** | `compressedBlob` is compiled per-platform. The shader *interface* is fully readable — see below. |
| **C# method bodies (IL2CPP)** | AOT-compiled to native ARM in `libil2cpp.so`. |

**Everything else IS readable — export all of it:**

| Data | Access | Verified on reference app |
|---|---|---|
| Texture2D, Sprite, Mesh, AudioClip, TextAsset | direct export | 305 / 557 / 554 / 21 / 1371 |
| **Font — real TTF/OTF bytes** | `m_FontData` | 13 fonts, valid files (LiberationSans 350 KB, Noto subsets, Orbitron…). **`m_FontData` may come back as a list of ints — `bytes()` it, and sniff the magic (`\x00\x01\x00\x00`/`true` → `.ttf`, `OTTO` → `.otf`).** An earlier pass hit a `TypeError` here and wrongly concluded fonts carry no data. Also capture `m_FontNames`, `m_FontSize`, `m_Ascent`, `m_LineSpacing`, `m_KerningValues` (266 pairs on LiberationSans), and the `m_Texture` atlas reference. |
| **Shader interface** | `m_ParsedForm` | Real name (`Toony Colors Pro 2/Hybrid Shader 2`, `RoyalSmash/UI/Coin-SheetAnimation`, `Cypher/VFX/Default`, `UI/HoleMask`, `Spine/SkeletonGraphic Additive`, `TextMeshPro/Distance Field With Shine`), the **full property table** (34 props on URP Simple Lit: `m_Name`, `m_Description` display label, `m_Type`, `m_DefValue_0_.._3_`, `m_DefTexture.m_DefaultName`, `m_Attributes`, `m_Flags`), subshader tags (`RenderType`, `RenderPipeline`, `UniversalMaterialType`), `m_LOD`, pass count, `m_KeywordNames`, `m_FallbackName`. That is enough to re-declare the shader exactly and re-author only the body. 45 shaders present. |
| **ParticleSystem — every module** | engine type, 43 fields | `InitialModule` (startLifetime/speed/size/color/rotation), `EmissionModule`, `ShapeModule`, `VelocityModule`, `ForceModule`, `ColorModule`, `ColorBySpeedModule`, `SizeModule`, `SizeBySpeedModule`, `RotationModule`, `RotationBySpeedModule`, `ClampVelocityModule`, `CollisionModule`, `SubModule`, `UVModule`, `lengthInSec`, `looping`. 218 systems. Plus `ParticleSystemRenderer` (material, render mode, sort mode). An earlier pass claimed "ayar verisi çıkmadı" — false. |
| **Colliders — exact geometry** | engine types | `BoxCollider` (`m_Center`, `m_Size`), `SphereCollider` (`m_Center`, `m_Radius`), `MeshCollider` (`m_Mesh`, `m_Convex`, `m_CookingOptions`, `m_InflateMesh`, `m_SkinWidth`), all with `m_IsTrigger`, `m_Material`, layer overrides. 1745 box + 985 mesh + 4 sphere. |
| **Joints** | engine type, 45 fields | `ConfigurableJoint`: `m_ConnectedBody`, `m_Anchor`, `m_Axis`, per-axis motion locks, `m_LinearLimit`, `m_AngularYLimit`/`ZLimit`, `m_AngularXDrive`/`YZDrive`, `m_BreakForce`, `m_BreakTorque`, `m_ConfiguredInWorldSpace`. This is the whole wrecking-ball/rope rig. |
| Rigidbody | engine type | mass, drag, angularDrag, useGravity, interpolate, collisionDetection, constraints |
| PhysicMaterial | engine type | **use the `m_`-prefixed names** (`m_DynamicFriction`, `m_StaticFriction`, `m_Bounciness`, `m_FrictionCombine`, `m_BounceCombine`); the unprefixed attributes return `None` |
| Material | engine type | all floats, colors, texture slots + tiling/offset, `m_ValidKeywords`, render queue |
| **AnimationClip** | engine type | `m_Name`, `m_SampleRate`, `m_WrapMode`, `m_Events`, and `m_ClipBindingConstant.genericBindings` (path hash, attribute hash, typeID) — always readable. Curve data: **legacy** clips expose `m_PositionCurves`/`m_RotationCurves`/`m_ScaleCurves`/`m_FloatCurves` directly (2 of 34 here); **Mecanim** clips hide it behind `m_MuscleClip.m_Clip` which is an `OffsetPtr` — deref with `.data` to reach `m_StreamedClip` / `m_DenseClip` (`m_FrameCount`, `m_CurveCount`, `m_SampleArray`) / `m_ConstantClip`. Verified: `.data` works, one clip had 84 streamed entries and 62 dense frames. Decoding those three containers is a known, documented format (see AssetStudio / AssetRipper implementations) — implement it, do not skip it. |
| **AnimatorController** | engine type | `m_TOS` (path-hash → readable name, which is also what resolves the clip bindings above), `m_AnimationClips`, `m_Controller.m_LayerArray`, `m_Controller.m_StateMachineArray` (`OffsetPtr` → `.data`), default values. 19 controllers. |
| **Project settings** (`globalgamemanagers`) | engine types | `PhysicsManager`, `Physics2DSettings`, `TimeManager` (fixed timestep), `QualitySettings` (all 6 tiers + mobile default), `GraphicsSettings` (44 fields incl. always-included shaders), `TagManager` (tags + all 32 layer names), `AudioManager`, `InputManager`, `RenderSettings` (fog, ambient, halo), `LightmapSettings`, `NavMeshSettings`, `BuildSettings` (build GUID, version). **This is the project configuration of the original game, recoverable in full.** Only `PlayerSettings` failed to parse (Unity 6 layout newer than UnityPy's tree) — fall back to the APK manifest for identity fields and record the gap. |
| UI layout | engine types | `Canvas` (render mode, sorting layer/order, pixel perfect, plane distance), `RectTransform` (anchors, pivot, sizeDelta), `CanvasGroup`, `SortingGroup`, `CanvasRenderer` |
| Renderers | engine types | `MeshRenderer`, `SkinnedMeshRenderer`, `SpriteRenderer`, `TrailRenderer` (43 fields: time, width curve, colour gradient, min vertex distance), `LineRenderer`, `ParticleSystemRenderer` |
| Scene objects | engine types | `Light`, `Camera`, `AudioListener`, `AudioSource`, `Animator`, `Animation` |
| GameObject / Transform hierarchy | walk `m_Component`, `m_Children` | full prefab structure |
| MonoScript | `m_ClassName`, `m_Namespace`, `m_AssemblyName` | full C# class inventory with **zero** IL2CPP tooling — 368 game classes recovered this way |

**Consequence for the prefab-structure question:** the *skeleton* is fully recoverable —
hierarchy, every engine component and its exact values, meshes, materials, colliders,
joints, particles, animators, UI rects. What is missing is only the **custom script field
values**. Say exactly that in the output; "prefab structure not recoverable" is wrong and
must not appear anywhere in the docs.

### 3.4 Per-type export rules

- **Texture2D** → PNG via `obj.read().image`. Objects with an empty `m_Name` will try to write to a directory path and raise `IsADirectoryError` — fall back to `unnamed_<path_id>.png`. **Record `m_TextureFormat`**: in the reference app 189/305 were uncompressed (RGBA32=4, RGB24=3, Alpha8=1 → pixel-perfect) and 116 were ASTC (48=4x4, 50=6x6, 51=8x8 → decoded, so re-compressing costs a second generation of loss). This distinction must reach the manifest and the report; it is the difference between "usable" and "usable with quality loss".
- **Sprite** → PNG via `.image`, **plus metadata that is otherwise lost**: `m_PixelsToUnits`, `m_Pivot`, `m_Border` (L,B,R,T), `m_Rect`. In the reference app **138 of 536 sprites had a non-zero 9-slice border** — importing without it visibly breaks every UI frame. Write `sprite-meta.json`.
- **Mesh** → OBJ via `.export()`. It emits `v`/`vt`/`vn`/`f` but **no `usemtl`/`mtllib`** — you must write a companion `.mtl` and the `usemtl` line yourself (see §4.3). Also lost: vertex colours, tangents (recomputable), bone weights.
- **AudioClip** → iterate `.samples` (a `{name: bytes}` dict) and write each. Verified output: 44.1 kHz / 16-bit / mono WAV, valid.
- **TextAsset** → raw bytes. **Detect level data**: in the reference app 1360 TextAssets had purely numeric names and were level JSON. Route numeric/`.json` ones to `levels/`, `.skel`/`.atlas` to `spine/`, the rest to `text/`.
- **Font** → `m_FontData` is empty for TextMeshPro SDF fonts (13/13 in the reference app). Emit nothing and say so rather than writing 0-byte files.
- **AnimationClip / AnimatorController** → currently **not exported at all**; this upgrade must add them (see §4.2).

### 3.5 Prefab / entity grouping — the core of this upgrade

For each interesting root GameObject, walk its transform subtree (depth-limit ~4, cap
the node count) and aggregate:

- `MeshFilter.m_Mesh` **and** `SkinnedMeshRenderer.m_Mesh` (missing the latter silently drops every rigged model — it dropped all 7 cannon meshes on the first pass).
- `MeshRenderer/SkinnedMeshRenderer/SpriteRenderer.m_Materials` → material name, shader keywords, and every `m_SavedProperties.m_TexEnvs` texture.
- Colliders (by type + count), `Rigidbody` values, `PhysicMaterial` reference.
- `MonoBehaviour` → resolve `m_Script` to its `MonoScript.m_ClassName` (the field values are unreadable but the *class list per object* is highly informative).
- Child GameObject names.

**Which roots are "interesting":**
1. Every distinct `Id` value found in the extracted level data (this yielded all 132 gameplay entities in the reference app, 100 % hit rate against GameObject names).
2. Name-pattern sweep for gameplay nouns the level data misses — the reference app hid `Magnet`, `Wormhole`/`Portal`, `Pinata`, `WreckingBall`, `Rope`, `BarrageBomb`, `Hammer` in remote levels; a regex over GameObject names found them all.
3. Player/tool objects: cannon/launcher/ball/paddle/vehicle-type names.
4. Anything referenced from the gameplay scene root.

**Broken-piece classification:** meshes matching `broken|_piece|_geo_\d+$` (case-insensitive)
go to the entity's `broken/` subfolder. In the reference app this cleanly separated 138
whole meshes from 910 piece references and revealed the single most important technical
finding of the whole analysis — the game uses **pre-modelled fracture pieces, not runtime
fracture**. Surface that as a derived insight in the digest.

**External references:** a `PPtr` with `m_FileID > 0` indexes `assets_file.externals[m_FileID - 1]`.
When that resolves to `Library/unity default resources`, the mesh is a **Unity built-in
primitive** (Sphere/Cube/Quad) — not missing, not encrypted. Report it as
`builtin:<external-name>` instead of letting it read as an extraction failure. Reference
app: `MagnetBlue`, `WreckingBall`, `Portal`.

**Procedural geometry:** an object with materials but no mesh anywhere in its subtree and
a script list containing tube/rope/mesh-generator classes is **generated at runtime**
(`Rope`, `TwoEndRope` → `TubeMeshGenerator` + Verlet). Record as `procedural`, not missing.

**Scale caveat:** exported OBJ is the raw mesh in local space with **no prefab Transform
applied**. `stoneSquare1x1_geo` measured exactly 1×1×1 (grid unit) but `Cannon_body`
measured 830×828×1200 because it was authored in centimetres and scaled ~0.01 by its
prefab. Capture each entity's root `m_LocalScale`/`m_LocalPosition` into `entity.json`
and state the caveat in the guide.

### 3.6 Scenes

Serialized scene files are `level0`, `level1`, `level2`, … Walk each scene's roots and
emit an indented tree of `GameObject [components, MB:ScriptName]`. On the reference app
this gave the entire meta-UI inventory (35 named Canvases → every screen and popup in the
game) and the gameplay scene's manager list — the single best input for reconstructing
game flow. Cheap: 40 KB of text for a 1778-object scene.

### 3.7 Level data

Numeric-named TextAssets are levels. Parse, then derive and write an analysis:
schema keys, entity id frequency, **first level each entity appears in** (= the mechanic
introduction curve), per-level move/difficulty/entity-count distributions, and duplicate
detection. On the reference app duplicate detection found 1360 files for 760 ids with
differing move counts — a live **A/B level-ladder test**, invisible any other way.

## 4. What to build

### 4.1 `scripts/unity-extract.py` (new, venv/UnityPy)

One entry point: `unity-extract.py <apk-or-xapk|dir> --out <game-assets-dir> [--work <dir>]`.

Phases, each independently skippable via flags: unpack → merge splits → load → export
by type → scene dump → level analysis → entity grouping → materials/physics/sprite-meta →
previews → manifest + README emission.

Must be **resumable and honest**: never claim an asset was written unless the file exists
on disk; count failures per type and put them in the manifest `notes`.

### 4.2 Deep capture — the "polish" layer (all new; none of this exists today)

These are what make a clone *look and feel* like the original rather than merely
function. Every one is verified readable in §3.3. Export all of them.

**Animation**
- `AnimationClip` → JSON: name, sample rate, wrap mode, events, and the resolved binding list (`m_ClipBindingConstant.genericBindings` path/attribute hashes resolved to names via the owning `AnimatorController.m_TOS`). Legacy curves exported directly; Mecanim clips decoded out of `m_MuscleClip.m_Clip.data` → `m_StreamedClip` / `m_DenseClip` / `m_ConstantClip`. Where a container cannot be decoded, emit the clip with `"curves": "partial"` and the reason — never drop it silently.
- `AnimatorController` → JSON: `m_TOS` name table, layers, state machines, states (name, speed, referenced clip), transitions with their conditions, default state.
- `Animator` on an entity → which controller drives it, `applyRootMotion`, culling mode. Write it into that entity's folder.

**Particles / VFX** — `particles/<System>.json` with **every module** (initial, emission,
shape, velocity, force, colour, colour-by-speed, size, size-by-speed, rotation,
rotation-by-speed, clamp-velocity, collision, sub-emitters, UV/sheet animation),
`lengthInSec`, `looping`, plus the `ParticleSystemRenderer` (material, render/sort mode,
alignment). Particle systems that live under an entity are additionally written into that
entity's folder. 218 systems in the reference app — this is a large share of the game's
visual identity and is currently thrown away entirely.

**Shaders** — `shaders/<Name>.json` per shader: real name, fallback, the full property
table (internal name, display label, type, default values, default texture, attributes,
flags), subshader tags, LOD, pass count, keyword list. Plus `shaders/README.md` grouping
them into: **Unity built-in / URP** (drop-in), **known commercial** (`Toony Colors Pro 2`,
`Spine/*`, `TextMeshPro/*` → name the Asset Store package to buy), and **custom to this
game** (`RoyalSmash/*`, `Cypher/*` → must be re-authored; the property table is the exact
spec to re-author against). Materials reference their shader by real name so nothing is
orphaned.

**Fonts** — write the actual `.ttf`/`.otf` files, plus `fonts/fonts.json` with family
names, size, ascent, line spacing, kerning-pair count and the atlas texture. Separately
list the TextMeshPro SDF atlases found among the textures and note that the TMP
`FontAsset` glyph tables themselves are MonoBehaviour data and therefore stripped — so
the workflow is: import the real TTF and regenerate the SDF asset in Unity.

**Colliders and joints** — into `entity.json`, exactly: every collider with its type,
`center`, `size`/`radius`, `isTrigger`, convex/cooking flags, and physic-material name;
every joint with connected body, anchor, axis, per-axis motion locks, limits, drives,
break force/torque. `ImportExtracted.cs` must rebuild these verbatim.

**UI** — `ui/` : per-canvas JSON with render mode, sorting layer/order, plane distance,
scaler settings, and the `RectTransform` (anchor min/max, pivot, anchored position,
sizeDelta) of every node in the tree. This is what makes a screen reconstructable rather
than merely screenshot-matched.

**Project settings** — `project-settings/` : one JSON per manager (physics, physics2d,
time, quality tiers, graphics, tags + all 32 layer names, audio, input, render settings,
lightmap, navmesh, build). Emit a `README.md` that names the handful of values that
actually differ from Unity defaults — in the reference app that was `gravity = -24`,
`defaultSolverIterations = 35`, `maxAngularSpeed = 50`, which is precisely the tuning a
clone would otherwise spend days guessing. If `PlayerSettings` fails to parse, record the
failure and fall back to the APK manifest for identity fields.

**Scene objects** — lights (type, colour, intensity, shadows), cameras (projection, FOV,
clear flags, culling mask, depth), audio sources/listener, render settings (fog, ambient)
per scene.

### 4.3 Directly-usable output — the "hazır hale getirme" requirement

Every exported group must be self-sufficient:

- **`.mtl` beside every `.obj`**, with `map_Kd` pointing at the co-located texture and the diffuse/specular values taken from the real material; append the matching `usemtl`/`mtllib` lines into the OBJ (UnityPy does not write them).
- **Textures copied into the entity folder**, not only referenced from a global pool. Disk is cheap; a self-contained folder is the whole point. Keep the global `textures/` pool too, and de-duplicate with hardlinks where the filesystem allows.
- **`entity.json`** per entity — a machine-readable rebuild recipe: meshes, broken pieces, materials (all float/colour/keyword values), texture slot → file mapping, colliders, rigidbody values, physic material, animator, root transform scale/position, scripts, child names, level usage count, first level.
- **`README.md`** per entity — the same thing in two paragraphs for a human.
- **`preview.png`** per entity — see §4.4.
- **`unity-import/ImportExtracted.cs`** — a Unity Editor script that walks the extracted tree, imports the meshes/textures, recreates materials from `entity.json` values, and rebuilds each entity as a prefab with its colliders and rigidbody settings applied. This is what turns a dump into something usable in an afternoon. Ship it with a short usage note; it does not need to handle every edge case, but it must run without errors on a well-formed extraction.
- **`IMPORT.md`** at the root of `game-assets/` — what is pixel-perfect, what was ASTC-decoded, which meshes lost their rig, which objects are built-in primitives or procedural, which importer flags to set (sRGB vs linear, normal-map, 9-slice borders from `sprite-meta.json`, PPU).

### 4.4 `scripts/render-mesh-preview.py` (new)

A ~60-line numpy + Pillow z-buffer renderer: load OBJ, isometric camera, per-face
Lambert shading, painter/z-buffer, PNG out. No 3D framework, no headless GL. Verified
working on 150 meshes in the reference app — output was immediately legible (cannon,
barrels, jars, columns all recognisable). Emit one `preview.png` per entity plus a
labelled contact sheet `_contactsheet_entities.png`, and equivalent contact sheets for
sprites and textures. These are the artifact that lets a human verify the extraction in
one glance instead of opening 500 files.

### 4.5 `scripts/unity-assets.sh` (rewrite)

Keep the same call signature (`unity-assets.sh <apk> <out-dir>`) so SKILL.md Phase 2d and
the existing tests keep working, but change the behaviour:

1. Ensure the extraction venv (call `setup-extraction-venv.sh`), then run
   `unity-extract.py` — **this is now the default path and it actually extracts.**
2. `ASSETRIPPER_CLI` stays an *optional supplement* for the cases UnityPy handles worse
   (bundled shaders, some scene reconstruction), never a prerequisite.
3. Exit codes: `2` usage error (unchanged), `3` venv/UnityPy unavailable **with install
   guidance** (unchanged shape so `test-unity-wrappers.sh` still passes after you update
   its expectations), `0` on success with a real manifest.
4. Delete the `UNITY_ASSETS_MANUAL` dead-end path, or demote it to a documented escape
   hatch — it must no longer be the only way the script exits 0.

### 4.6 Output layout (specify this exactly in the guide and honour it in code)

```
work/<pkg>/game-assets/
  manifest.json                 # module-contract shape; expected/extracted/by_type + notes
  coverage-report.md            # via gen-coverage-report.py
  IMPORT.md                     # how to import, what is lossy, what is missing
  ARCHITECTURE.md               # MonoScript class inventory grouped by assembly + namespace
  entities/
    <EntityName>/
      <mesh>.obj  <mesh>.mtl
      broken/     <piece>.obj …
      textures/   <texture>.png …
      animations/ <clip>.json  <controller>.json
      particles/  <system>.json
      preview.png
      entity.json               # incl. colliders, joints, rigidbody, animator, transform
      README.md
  scenes/
    <scene>.tree.txt            # indented GameObject/component tree
    scenes.json                 # scene list + root inventory + canvas/screen names
    <scene>.objects.json        # lights, cameras, audio, render settings per scene
  levels/
    <id>.json                   # raw level data, original names preserved
    level-analysis.json         # entity-first-appearance curve, distributions, A/B duplicates
  animations/
    clips/<clip>.json           # every clip, incl. ones not bound to an entity
    controllers/<ctrl>.json     # states, transitions, conditions, TOS name table
  particles/    <system>.json   # all 218, entity-owned ones also copied into the entity
  shaders/      <shader>.json + README.md   # name, props, tags, keywords; buy-vs-reauthor grouping
  ui/           <canvas>.json   # canvas + full RectTransform tree
  project-settings/
    physics.json  time.json  quality.json  graphics.json  tags-and-layers.json
    audio.json  input.json  render-settings.json  build.json  README.md
  sprites/      *.png + sprite-meta.json
  textures/     *.png + texture-formats.json     # per-texture format + lossless/ASTC flag
  audio/        *.wav
  fonts/        *.ttf *.otf + fonts.json
  spine/        *.skel *.atlas
  text/         *.txt
  materials.json
  physics.json                  # PhysicsManager + PhysicMaterials + per-entity rigidbodies
  unity-import/ImportExtracted.cs
  _contactsheet_entities.png  _contactsheet_sprites.png  _contactsheet_textures.png
```

Grouping rule to encode: **things that combine into one object share a folder** (mesh +
its pieces + its textures + its material values + its animations + its physics). Things
that are used across the whole game stay in a shared pool (audio, fonts, spine, the
global texture/sprite pools, the level database). That is the distinction the folder
layout above expresses — follow it.

### 4.7 Docs to update

- `references/unity-re-guide.md` — replace the "AssetRipper is undrivable, defer" section with the UnityPy pipeline, **the full recoverability matrix from §3.3 including the engine-type-vs-user-type rule**, the ASTC/rig/scale/9-slice caveats, and the built-in-primitive and procedural-geometry cases. The guide must state plainly that prefab structure, colliders, joints, particles, animations, fonts, shader interfaces and project settings ARE recoverable, and that only MonoBehaviour field values, shader bytecode and IL2CPP method bodies are not.
- **New** `references/unity-asset-extraction-guide.md` — the output-layout contract, the entity-grouping algorithm, and the "what is directly usable vs what needs re-authoring" table.
- `references/engines/module-contract.md` — add `entities/`, `scenes/`, `levels/`, `materials.json`, `physics.json`, `IMPORT.md`, `ARCHITECTURE.md` to the required artifact list, so Unreal/Godot modules aim at the same shape.
- `references/report-template.md` §4b "Game Assets" — expand from two lines to a real section: per-type counts, entity count, lossy-vs-lossless texture split, animation coverage, what is missing and why, and the derived findings (fracture strategy, shader family, physics tuning constants).
- `SKILL.md` Phase 2c — the Unity gate must now check for the **extraction venv / UnityPy** as the primary requirement; AssetRipper drops to optional. Phase 2d — the subagent instructions must call the new pipeline and return only the summary + paths (never asset content). Keep the existing pause-and-ask-the-user behaviour when a tool is genuinely missing.
- `README.md` (plugin) — one paragraph on what a Unity run now produces.

### 4.8 Tests

Offline, fixture-based, in the existing style:

- `test-unity-wrappers.sh` — update expectations for the rewritten `unity-assets.sh` (usage → 2, missing venv → 3 with guidance).
- `test-unity-extract.py` — unit-test the **pure** functions against synthetic inputs, no UnityPy needed: split-file merge ordering, broken-piece classification regex, entity-folder naming/collision handling, `.mtl` emission, `entity.json` shape, manifest counting (never over-claims), external-reference → `builtin:` classification, level duplicate detection.
- `test-render-mesh-preview.py` — feed a hand-written 12-triangle cube OBJ, assert a non-blank PNG of the expected size is produced.
- Add a fixture: `tests/fixtures/unity-sample/` with a tiny synthetic OBJ, a fake split-file set, and a small level JSON pair (one duplicate) so the analysis path is covered.
- An integration test that runs the real pipeline **only when `CLONE_APP_SAMPLE_APK` is set**, and skips cleanly otherwise.
- `smoke-structure.sh` — register every new file.
- `requirements-extraction.txt` — add `numpy` and `Pillow` next to UnityPy.

## 5. Guardrails

- **Do not silently degrade.** Every skipped or failed asset lands in `manifest.json` notes and in `coverage-report.md`. Extraction that half-worked must never read as complete.
- **Do not fabricate.** If a value is not readable (MonoBehaviour fields, shader source), the artifact says so explicitly. No inferred numbers presented as extracted ones.
- **Keep the legal stance already in the repo** and sharpen it with the technical reality: extracted assets are reference material; the *transferable* output is the structure — level schema, physics constants, entity taxonomy, mechanic-introduction curve, architecture map.
- **Context discipline:** the extraction runs in the Phase 2d subagent and returns a summary plus paths only. Raw asset content must never enter the orchestrator's context.
- Engine-agnostic where free: `unity-extract.py` is Unity-specific, but the output layout, manifest shape, and grouping rule belong to the module contract so Unreal/Godot modules can match them later.

## 6. Definition of done

1. `bash plugins/clone-app/tests/run-all.sh` passes.
2. `git status --porcelain plugins/android-reverse-engineering/` prints nothing.
3. On a real Unity XAPK, `bash unity-assets.sh <xapk> <out>` exits 0 and produces the §4.6 tree with a manifest whose counts match the files actually on disk.
4. `entities/<Name>/` folders are self-contained: mesh + pieces + textures + material values + colliders + joints + rigidbody + animations + particles + preview + `entity.json` + `README.md`.
5. `IMPORT.md` correctly states which textures are lossless vs ASTC-decoded, which meshes lost rigs, which objects are built-in primitives or procedural.
6. `ImportExtracted.cs` runs in a fresh Unity project against the extraction without errors and rebuilds prefabs **with their colliders, rigidbody values and joints applied**.
7. The docs in §4.7 describe what the code actually does — no aspirational text.
8. **Nothing in §3.3's "readable" column is missing from the output.** Specifically: real font files exist, every particle system has a JSON, every shader has its property table, every clip and controller is exported, collider/joint geometry is in `entity.json`, and `project-settings/` names the values that differ from Unity defaults.
9. The only things the docs may describe as unrecoverable are the three in §3.3: MonoBehaviour/ScriptableObject field values, shader HLSL/bytecode, and IL2CPP method bodies. Any other "not recoverable" claim is a bug in the docs.

## 7. Work order

Plan first, then implement in this order, committing per step:
`unity-extract.py` core (unpack/merge/load/export) → entity grouping → materials/physics/
sprite-meta → **fonts (real TTF/OTF)** → **shaders (property tables)** → **particles** →
**colliders + joints into `entity.json`** → **animations (clips + controllers, incl. Mecanim
container decode)** → **UI rects** → **project settings** → previews + contact sheets →
`.mtl`/`entity.json`/`README`/`IMPORT.md` emission → `ImportExtracted.cs` →
`unity-assets.sh` rewrite → docs → tests.

The five middle steps in bold are the "polish layer" — they are what separates a clone
that works from a clone that feels like the original. Do not defer them to a later pass.

Validate against a real package as you go: `com.cyphergames.royalsmash` is already
downloaded at `/Users/fatih.bulut/PythonWorks/new_market_reseaarch/work/com.cyphergames.royalsmash/app.xapk`,
and a manually-produced reference extraction (the exact target output) sits beside it in
`assets/` — compare against it.
