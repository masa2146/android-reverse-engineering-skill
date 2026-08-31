# Unity Asset Extraction Guide

The output contract for `unity-assets.sh` → `unity-extract.py`. Read this when
you need to know what a Unity run produces, where a given asset lives, and what
still has to be re-authored by hand.

## The governing rule

**Unity engine types ship their type tree inside the serialized file, so every
field is readable. Only user types (MonoBehaviour / ScriptableObject) are
stripped in an IL2CPP release build.**

That single fact decides everything below. Colliders, joints, particles,
animations, shader interfaces, fonts, UI rects and project settings are engine
types — they come out complete. Balance tables in a `ScriptableObject` do not.

## Grouping rule

**Things that combine into one object share a folder. Things used across the
whole game stay in a shared pool.**

An entity folder holds its mesh, its fracture pieces, its textures, its material
values, its colliders/joints/rigidbody, its animations and particles, a preview
and a rebuild recipe. Audio, fonts, Spine data, the level database and the global
texture/sprite pools are shared, so they stay at the top level.

## Output layout

```
game-assets/
  manifest.json          module-contract shape; expected/extracted/by_type + notes
  coverage-report.md     gen-coverage-report.py output (honest covered/partial/missing)
  IMPORT.md              how to import, what is lossy, what is missing
  ARCHITECTURE.md        MonoScript class inventory by assembly + namespace
  entities/
    <Entity>/
      <mesh>.obj + <material>.mtl      mtllib/usemtl already wired in
      broken/<piece>.obj               pre-modelled fracture debris
      textures/<texture>.png           copies, so the folder stands alone
      animations/<clip|controller>.json
      particles/<system>.json
      preview.png
      entity.json                      machine-readable rebuild recipe
      README.md                        the same thing for a human
    _index.json
  scenes/<scene>.tree.txt              indented GameObject/component tree
  scenes/<scene>.objects.json          lights, cameras, audio, render settings
  scenes/scenes.json
  levels/<id>.json + level-analysis.json
  animations/clips/*.json  animations/controllers/*.json
  particles/*.json
  shaders/*.json + README.md           buy-vs-re-author grouping
  ui/<canvas>.json                     canvas + full RectTransform tree
  project-settings/*.json + README.md  README names the non-default values
  sprites/*.png + sprite-meta.json
  textures/*.png + texture-formats.json
  audio/*.wav   fonts/*.ttf|otf + fonts.json   spine/*   text/*
  materials.json   physics.json
  unity-import/ImportExtracted.cs + README.md
  _contactsheet_entities.png  _contactsheet_sprites.png  _contactsheet_textures.png
```

## Entity grouping algorithm

Grouping must not depend on a game's naming conventions — plenty of titles ship
meshes called `BezierCurve.041`. So discovery is **structural first**:

1. **Candidates**, in order of reliability:
   - **structural** — every content-bearing prefab root in the package: a
     transform with no parent, living outside a scene file, whose subtree
     contains a MeshFilter / SkinnedMeshRenderer / SpriteRenderer / MeshRenderer
     / ParticleSystem / Trail- or LineRenderer. This is engine-level and works
     for any game and genre.
   - **level data** — every distinct entity `Id` the level database names.
   - **name hints** — a gameplay-noun sweep (`ENTITY_HINT_RE`) minus obvious UI
     names (`UI_NOISE_RE`), which catches objects embedded in a scene rather
     than shipped as prefabs (a cannon parented under the gameplay scene root).
   `--max-entities` caps the total; anything dropped by the cap is recorded in
   the manifest notes, never silently.
2. **Walk** each candidate root's transform subtree (depth ≤ 5, ≤ 400 nodes),
   collecting `MeshFilter.m_Mesh` **and** `SkinnedMeshRenderer.m_Mesh` (missing
   the latter silently drops every rigged model), renderer materials and their
   texture slots, colliders, joints, rigidbody, animator, particle systems,
   sprites, and `MonoScript` class names.
3. **Classify meshes**: names matching `broken|_piece|_geo_\d+$|_shard` are
   fracture debris and go to `broken/`.
4. **Prune**: candidates the level data never named are dropped unless they have
   real content (geometry, colliders, joints, particles, sprites, a built-in
   primitive reference, or a procedural-generator script). Level-named entities
   are always kept — an empty one is itself a finding.

## `geometry_status` — why an entity may have no mesh

| Status | Meaning |
|---|---|
| `extracted` | meshes written to the folder |
| `builtin-primitive` | the mesh PPtr resolves to `Library/unity default resources` — a Unity Sphere/Cube/Quad. **Nothing is missing**; recreate with a primitive plus the recorded material values |
| `procedural` | no static mesh exists; the original generates it at runtime (tube/rope/Verlet generators). Reimplement the generator |
| `particle-effect` | a VFX prefab: no mesh by design. Every particle module value is under `particles/`, so it can be rebuilt exactly |
| `sprite-based` | 2D object, no 3D geometry |
| `external-reference` | points at a file outside the package (CDN/Addressable content not shipped in the APK) |
| `empty` | genuinely nothing found — reported, not hidden |

## What is directly usable vs what needs work

| Asset | State on disk | Work required |
|---|---|---|
| Meshes | OBJ + MTL, geometry intact | apply `entity.json.transform.localScale` — some models are authored in centimetres; recompute tangents; skinning/bone weights and vertex colours are not carried by OBJ |
| Textures | PNG | set sRGB-vs-linear and normal-map flags by hand. Check `texture-formats.json`: uncompressed sources are pixel-perfect, ASTC/ETC/DXT sources were decoded and re-compressing costs a second generation |
| Sprites | PNG | apply `sprite-meta.json` (pivot, pixels-per-unit, 9-slice `border_LBRT`) or UI frames stretch |
| Audio | PCM WAV | none |
| Fonts | real TTF/OTF | regenerate TMP SDF assets from them; the original `TMP_FontAsset` glyph tables are ScriptableObject data and are stripped |
| Levels | plain JSON | none — engine-agnostic |
| Materials | every float/colour/keyword/texture slot | re-apply onto your own shader |
| Shaders | interface only | built-in → drop-in; commercial → buy the named package; custom → re-author the body against the recorded property table |
| Particles | every module as JSON | re-enter into a `ParticleSystem`; no importer does this automatically |
| Animations | clips + controllers as JSON | check `curves_status` per clip; Mecanim curves are decoded from Streamed/Dense/Constant containers, legacy clips come out directly |
| Physics | `physics.json` + `project-settings/` | copy the constants **before** hand-tuning; `project-settings/README.md` lists what differs from Unity defaults |
| Prefab structure | hierarchy + every engine component value in `entity.json` | `unity-import/ImportExtracted.cs` rebuilds it; custom script field values are the one real gap |

## Genuinely unrecoverable — exactly three things

1. **MonoBehaviour / ScriptableObject field values** — type trees stripped in an
   IL2CPP release build. This is what costs you balance tables, tuning configs
   and LiveOps parameters. Class *names* survive in `ARCHITECTURE.md`.
2. **Shader HLSL / compiled bytecode** — compiled per platform.
3. **C# method bodies** — AOT-compiled into `libil2cpp.so`.

Any other "not recoverable" claim in a report is a bug. If something is missing
it is because it was not extracted, not because it could not be.

## Honesty rules the extractor enforces

- `manifest.json.assets.extracted` is derived from the per-type counts, so it can
  never claim more than was written.
- Every read/decode failure is counted by type and lands in `manifest.json`
  notes and therefore in `coverage-report.md`.
- Built-in primitives and procedural geometry are reported as findings, never as
  missing assets.
- Lossy-decoded textures are flagged individually in `texture-formats.json`.

## Legal

Extracted art is copyrighted. The transferable output is the **structure** —
level schema, physics constants, entity taxonomy, mechanic-introduction curve,
architecture map. Treat the art as reference and recreate it in the same style.

## The prefab node tree (`entity.json` → `nodes`)

An entity folder is **not** a bag of OBJs. Each `entity.json` carries `nodes`: the
object's real hierarchy, one entry per GameObject.

| field | meaning |
|---|---|
| `name` | the node's name in the original prefab |
| `parent` | index into `nodes`; `-1` for the root |
| `depth` | distance from the root |
| `localPosition` / `localRotation` / `localScale` | the node's own transform |
| `mesh` / `mesh_file` | the mesh this node carries, and the OBJ on disk |
| `materials` | material names **in slot order** — slot order maps to sub-mesh order |
| `active` | whether the node ships enabled |
| `fracture` | debris: the node's own name says so, or an ancestor (`Break`/`Crack`/`Debris`/`Shatter`) does |

**Why it exists.** Without it a folder holds the body, the cracked variant and the
fracture debris side by side with nothing saying which is which — so a rebuild
picks the largest mesh, throws away the planks and the trim, and then draws the
missing parts by hand. A multi-plank block (`PixelWoodBlockPlankModel`,
`BreakWoodPlanks`) cannot be reconstructed from a single merged body at all.

**Rules:**
- Build the hierarchy from `nodes`, not from `whole_mesh_files`. The flat list is a
  convenience index, not a recipe.
- Apply each node's local transform. Parts stacked at the origin are the tell that
  this was skipped.
- Assign `materials` **in order** to `sharedMaterials`. One material on a
  multi-slot renderer paints the whole object.
- Parent `fracture` nodes under a disabled root; they are the break state, not the
  intact object.
- `materials.mtl` in the entity folder carries **every** material of the entity,
  and each OBJ's `usemtl` names the material of the node that carries it.

`unity-import/ImportExtracted.cs` consumes all of this: it rebuilds the tree,
applies transforms, creates one Unity material per extracted material with its own
textures, and puts debris under a disabled `Broken` root. It falls back to the old
flat build only when `nodes` is absent (an older extraction).
