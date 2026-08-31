#!/usr/bin/env python3
"""Generate the asset-usage guide set from a clone-app extraction.

    python3 gen-asset-guide.py <extracted-dir> --out <docs-dir> [--project-name NAME]

Emits, into <docs-dir>:
    ASSET-INDEX.tsv        one greppable line per asset  (Tier 3 — machine)
    ASSET-CATALOG.md       one card per entity           (Tier 2 — on demand)
    COMPOSITION-RULES.md   how pieces combine into one object
    COMPONENT-RECIPES.md   archetype -> Unity component stack
    ASSET-RULES.md         the resolution protocol + prohibitions
    CLAUDE-SECTION.md      the block to paste into CLAUDE.md (Tier 1)

Handles both extraction layouts:
    new     <extracted>/game-assets/entities/<Name>/entity.json
    legacy  <extracted>/game-assets-legacy/assets/entities/<Name>/info.json

The point of this file: an AI that cannot resolve "the red shooter" to
`entities/Shooter/Cube.011.obj` will draw its own. Every output here exists to
make that resolution mechanical instead of imaginative.
"""

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict

# --------------------------------------------------------------------------- #
# layout discovery
# --------------------------------------------------------------------------- #

def find_layout(extracted):
    """Return (game_dir, entity_glob_name, layout_tag)."""
    new = os.path.join(extracted, "game-assets")
    if os.path.isdir(os.path.join(new, "entities")):
        return new, "entity.json", "new"
    legacy = os.path.join(extracted, "game-assets-legacy", "assets")
    if os.path.isdir(os.path.join(legacy, "entities")):
        return legacy, "info.json", "legacy"
    sys.exit(f"no entities/ under {extracted}")


def load_entities(game_dir, fname):
    ents = []
    root = os.path.join(game_dir, "entities")
    for name in sorted(os.listdir(root)):
        p = os.path.join(root, name, fname)
        if not os.path.isfile(p):
            continue
        try:
            d = json.load(open(p))
        except Exception:
            continue
        d["_dir"] = os.path.join("entities", name)
        d.setdefault("entity", name)
        ents.append(d)
    return ents


# --------------------------------------------------------------------------- #
# normalisation — the two layouts disagree on field names
# --------------------------------------------------------------------------- #

def norm(e, game_dir):
    """Flatten either layout into one shape."""
    name = e.get("entity") or os.path.basename(e["_dir"])

    meshes = e.get("whole_mesh_files") or e.get("whole_meshes") or []
    meshes = [m if str(m).endswith(".obj") else f"{m}.obj" for m in meshes]
    broken = e.get("broken_piece_files") or e.get("broken_pieces") or []

    mats_raw = e.get("materials")
    if isinstance(mats_raw, dict):
        mat_slots = list(mats_raw)
        tex = []
        for m in mats_raw.values():
            if isinstance(m, dict):
                tex += list((m.get("texture_slots") or {}).values())
    else:
        mat_slots = list(mats_raw or [])
        tex = list(e.get("textures") or [])
    # aggregated slot map on the new layout
    for v in (e.get("texture_slots") or {}).values():
        tex.append(v)
    tex = sorted({os.path.basename(str(t)) for t in tex if t})

    colliders = e.get("colliders") or []
    return {
        "name": name,
        "dir": e["_dir"],
        "meshes": meshes,
        "broken": broken,
        "mat_slots": mat_slots,
        "textures": tex,
        "colliders": colliders,
        "rigidbody": e.get("rigidbody"),
        "joints": e.get("joints") or [],
        "animator": e.get("animator"),
        "animations": e.get("animations") or [],
        "particles": e.get("particles") or [],
        "sprites": e.get("sprites") or [],
        "renderers": e.get("renderers") or [],
        "scripts": e.get("scripts") or [],
        "children": e.get("children") or [],
        "geometry_status": e.get("geometry_status") or "",
        "nodes": e.get("nodes") or [],
        "levels_used": e.get("levels_used"),
        "first_level": e.get("first_level"),
    }


# --------------------------------------------------------------------------- #
# OBJ group count — the single most common "half the mesh is missing" trap
# --------------------------------------------------------------------------- #

def obj_groups(path):
    try:
        with open(path, errors="ignore") as fh:
            return sum(1 for line in fh if line.startswith("g "))
    except OSError:
        return 0


# --------------------------------------------------------------------------- #
# archetype + aliases — this is what makes semantic lookup work
# --------------------------------------------------------------------------- #

ARCHETYPES = [
    ("grid-cell",   r"\bpixel\b|\bhardpixel\b|\bblock\b|colorbox|\bcube\b(?!\.\d)"),
    ("shooter",     r"shooter|cannon|\bpig\b|launcher"),
    ("projectile",  r"projectile|missile|\bball\b|bullet|\bammo\b"),
    ("rail",        r"conveyor|\brail\b|\btrack\b|belt|carrier"),
    ("slot",        r"\bslot\b|\btray\b|bench|queue"),
    ("obstacle",    r"ice|wood|stone|cage|lock|\bkey\b|gate|\bwall\b|curtain|blocker|door|barrier"),
    ("layered-hp",  r"matryoshka|biscuit|accordion|totem|egg|bean|bead|pumpkin|jamjar|\bcan\b|split"),
    ("actor",       r"spaceship|\bufo\b|snake|crossbow|hammer|mallet|music|pipe|bouncer|magnet"),
    ("scenery",     r"scenery|ground|environment|table|column|backdrop|combined"),
    ("vfx",         r"\bfx\b|effect|particle|muzzle|spark|glow|trail"),
    ("ui",          r"button|panel|popup|view|icon|banner|badge|shop|bundle|pass|mission|hud"),
]

COLOR_TR = {
    "red": "kirmizi", "green": "yesil", "blue": "mavi", "yellow": "sari",
    "black": "siyah", "white": "beyaz", "purple": "mor", "pink": "pembe",
    "orange": "turuncu", "gold": "altin", "brown": "kahverengi", "gray": "gri",
    "grey": "gri", "ice": "buz", "wood": "tahta", "stone": "tas",
}
NOUN_TR = {
    "shooter": "atici", "conveyor": "konveyor bant ray", "slot": "yuva",
    "pixel": "piksel blok", "block": "blok", "cage": "kafes", "lock": "kilit",
    "key": "anahtar", "gate": "kapi", "wall": "duvar", "ball": "top",
    "cannon": "top topu", "ground": "zemin", "arrow": "ok", "shadow": "golge",
    "button": "dugme", "loader": "yukleyici", "machine": "makine",
}


def archetype_of(name):
    low = name.lower()
    for tag, pat in ARCHETYPES:
        if re.search(pat, low):
            return tag
    return "misc"


def tokens_of(name):
    parts = re.split(r"[^A-Za-z0-9]+", name)
    out = []
    for p in parts:
        if not p:
            continue
        # split CamelCase and trailing digits
        for piece in re.findall(r"[A-Z]?[a-z]+|\d+|[A-Z]+(?![a-z])", p):
            out.append(piece.lower())
    return [t for t in out if len(t) > 1 and not t.isdigit()]


def aliases_of(name, archetype):
    toks = set(tokens_of(name))
    al = set(toks)
    al.add(archetype)
    for t in list(toks):
        if t in COLOR_TR:
            al.add(COLOR_TR[t])
        if t in NOUN_TR:
            al.update(NOUN_TR[t].split())
    return sorted(a for a in al if a)


# --------------------------------------------------------------------------- #
# component recipe inference
# --------------------------------------------------------------------------- #

def recipe_of(e):
    """What Unity components this object actually needs. Derived, not guessed."""
    comps = []
    if e["meshes"]:
        comps += ["MeshFilter", "MeshRenderer"]
    if e["sprites"] and not e["meshes"]:
        comps += ["SpriteRenderer"]
    elif e["sprites"]:
        comps += ["SpriteRenderer (child)"]
    if e["particles"]:
        comps += ["ParticleSystem", "ParticleSystemRenderer"]
    for c in e["colliders"]:
        cn = c.get("type") if isinstance(c, dict) else str(c)
        comps.append(cn or "Collider")
    if e["rigidbody"]:
        comps.append("Rigidbody")
    if e["joints"]:
        comps.append("Joint")
    if e["animator"] or e["animations"]:
        comps.append("Animator")
    if not comps:
        comps = ["(logical node — Transform only)"]
    return comps


# --------------------------------------------------------------------------- #
# emit
# --------------------------------------------------------------------------- #

def write_index(rows, out):
    p = os.path.join(out, "ASSET-INDEX.tsv")
    with open(p, "w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["name", "archetype", "dir", "meshes", "mesh_groups",
                    "material_slots", "textures", "components", "children",
                    "nodes", "mesh_nodes", "fracture_nodes", "node_meshes",
                    "levels_used", "first_level", "aliases"])
        for r in rows:
            w.writerow([
                r["name"], r["archetype"], r["dir"],
                ";".join(r["meshes"]) or "-",
                ";".join(f'{m}:{g}' for m, g in r["groups"].items()) or "-",
                ";".join(r["mat_slots"]) or "-",
                ";".join(r["textures"]) or "-",
                ";".join(r["recipe"]),
                ";".join(r["children"]) or "-",
                len(r["nodes"]) or "-",
                sum(1 for n in r["nodes"] if n.get("mesh_file")) or "-",
                sum(1 for n in r["nodes"] if n.get("fracture")) or "-",
                ";".join(f"{n['name']}={n['mesh_file']}"
                         for n in r["nodes"] if n.get("mesh_file")) or "-",
                r["levels_used"] if r["levels_used"] is not None else "-",
                r["first_level"] if r["first_level"] is not None else "-",
                " ".join(r["aliases"]),
            ])
    return p


def write_catalog(rows, out, project, layout):
    by = defaultdict(list)
    for r in rows:
        by[r["archetype"]].append(r)
    lines = [
        f"# Asset Catalog — {project}",
        "",
        "> Generated by `gen-asset-guide.py`. One card per extracted object.",
        "> **Do not draw anything that has a card here.** If a card exists, the",
        "> object exists; find it, do not recreate it.",
        "",
        f"Layout: `{layout}` · {len(rows)} entities",
        "",
        "Lookup order: grep `ASSET-INDEX.tsv` first (fast, machine), then read the",
        "card here for composition and component detail.",
        "",
        "## Multi-group meshes — read this before loading any OBJ",
        "",
        "`mesh_groups` counts `g ` lines in the OBJ. **A count > 1 means Unity's",
        "`LoadAssetAtPath` returns only the FIRST group** — you get part of the object",
        "and conclude the asset is broken. Load all sub-meshes explicitly.",
        "",
    ]
    for arch in sorted(by):
        lines.append(f"\n---\n\n## {arch}  ({len(by[arch])})\n")
        for r in sorted(by[arch], key=lambda x: x["name"]):
            lines.append(f"### `{r['name']}`\n")
            lines.append(f"- **dir:** `{r['dir']}/`")
            if r["meshes"]:
                ms = ", ".join(
                    f"`{m}`" + (f" **({r['groups'][m]} groups!)**" if r["groups"].get(m, 0) > 1 else "")
                    for m in r["meshes"])
                lines.append(f"- **meshes:** {ms}")
            if r["broken"]:
                lines.append(f"- **fracture pieces:** {len(r['broken'])}")
            if r["mat_slots"]:
                lines.append(f"- **material slots ({len(r['mat_slots'])}):** " +
                             ", ".join(f"`{m}`" for m in r["mat_slots"]))
            if r["textures"]:
                lines.append(f"- **textures:** " + ", ".join(f"`{t}`" for t in r["textures"]))
            lines.append(f"- **components:** " + ", ".join(f"`{c}`" for c in r["recipe"]))
            if r["children"]:
                lines.append(f"- **children ({len(r['children'])}):** " +
                             ", ".join(f"`{c}`" for c in r["children"][:14]) +
                             (" …" if len(r["children"]) > 14 else ""))
            if r["levels_used"] not in (None, "", 0):
                lines.append(f"- **used in {r['levels_used']} levels**, first appears at level "
                             f"**{r['first_level']}**")
            if r["geometry_status"] and r["geometry_status"] != "extracted":
                lines.append(f"- **geometry_status:** `{r['geometry_status']}` — "
                             "this is a finding, not a missing file (built-in primitive / "
                             "procedural / external reference).")
            lines.append(f"- **preview:** `{r['dir']}/preview.png`")
            lines.append("")
    p = os.path.join(out, "ASSET-CATALOG.md")
    open(p, "w").write("\n".join(lines))
    return p


def write_rules(out, project, game_dir, rows, layout):
    multi = [r for r in rows if any(g > 1 for g in r["groups"].values())]
    nfiles = sum(1 for r in rows for g in r["groups"].values() if g > 1)
    nomesh = [r for r in rows if not r["meshes"] and not r["sprites_flag"]]
    composite = [r for r in rows if len(r["children"]) >= 3]
    multislot = [r for r in rows if len(r["mat_slots"]) > 1]
    txt = f"""# Asset Rules — {project}

> Tier-2 file. Read this once at the start of any task that puts something on
> screen. It is the protocol, not the data.

## The one rule

**Never invent an asset.** Every visual in this game already exists in the
extraction. If you cannot find it, the lookup failed — the asset did not.

Historically, *every* "this doesn't exist, I'll draw it" call has been wrong.
The causes were always one of: a wrong constant, taking group 1 of a multi-group
OBJ, mistaking a sprite for a mesh, or searching the wrong name.

## Asset resolution protocol

Run these in order. Stop at the first hit.

1. **grep the index** — fastest, covers aliases (name, archetype, meshes, group
   counts, material slots, textures, components, children, aliases — all on one line):
   ```
   grep -i '<word>' Docs/assets/ASSET-INDEX.tsv
   ```
2. **grep the scene tree** — an object is often named by its *scene node*, not by
   its file:
   ```
   grep -i '<word>' {os.path.abspath(game_dir)}/scenes/*.tree.txt
   ```
3. **grep material names** — surfaces are named by material:
   ```
   python3 -c "import json;print([k for k in json.load(open('{os.path.abspath(os.path.join(game_dir,'materials.json'))}')) if '<word>'.lower() in k.lower()])"
   ```
4. **try synonyms.** The extraction's vocabulary differs from yours:
   `slot / tray / carrier / bench` · `arrow / chevron` · `loader / starter /
   machine` · `rail / track / conveyor / belt` · `pig / shooter / launcher`.
5. **look at `preview.png`** in the entity folder. Names lie; renders do not.

**If all five fail:** do not draw. Write down what you searched and why it might
be named differently, then ask. A wrong guess costs more than a question.

## The node tree supersedes the flat lists

`entity.json` → `nodes` is the object's real hierarchy: parent, local transform,
mesh file, materials **in slot order**, active, fracture. Build from it.
`whole_mesh_files` and `materials` are flat indexes kept for lookup — an object
rebuilt from them has its parts stacked at the origin wearing the wrong surface.

## Three checks before you place anything

1. `preview.png` — what does it actually look like?
2. `grep -c '^g ' <file>.obj` — **{len(multi)} objects here have multi-group OBJs**
   ({nfiles} files in total). More than one group means `LoadAssetAtPath` hands you
   a fragment.
3. `materials.json` floats — `_UseOutline`, `_ReceiveShadowsOff`, `_SpecularType`,
   `_Cull`. Most "it looks wrong" bugs are an unread float, not a bad mesh.

## Composition facts for this extraction

- **{len(multislot)} objects carry more than one material slot.** The slot *order*
  matters: it maps to sub-mesh order. Assigning one material to a multi-slot
  renderer silently paints the whole object.
- **{len(composite)} objects are composites** (3+ children). Their `children` list
  in the catalog is the prefab hierarchy — rebuild it, do not flatten it.
- **{len(nomesh)} objects have no mesh of their own.** They are sprite-only,
  particle-only or logical nodes. Not missing — differently shaped.
- Objects whose `geometry_status` is not `extracted` reference a Unity built-in
  primitive, are generated procedurally, or point outside the bundle. These are
  **findings, not gaps** — recreate with a primitive plus the recorded material.

## Never do these

1. Draw a mesh, sprite or effect before running the 5-step protocol.
2. Load a multi-group OBJ and assume you got the whole object.
3. Assign a single material to a multi-slot renderer.
4. Flatten a composite's child hierarchy.
5. Guess a constant (radius, scale, spacing, palette order) that is measurable in
   the extraction.
6. Tint a sprite whose texture already carries its own colour.
7. Add a collider to something the layer matrix says never collides.
"""
    p = os.path.join(out, "ASSET-RULES.md")
    open(p, "w").write(txt)
    return p


def write_recipes(rows, out, project):
    by = defaultdict(list)
    for r in rows:
        by[r["archetype"]].append(r)
    lines = [f"# Component Recipes — {project}", "",
             "> Which Unity components each family of object actually needs, derived",
             "> from the extracted component data — not guessed.", "",
             "| archetype | count | typical components | notes |",
             "|---|---|---|---|"]
    for arch in sorted(by):
        rs = by[arch]
        c = Counter()
        for r in rs:
            c[" + ".join(r["recipe"])] += 1
        top = c.most_common(1)[0][0]
        withrb = sum(1 for r in rs if r["rigidbody"])
        withcol = sum(1 for r in rs if r["colliders"])
        note = []
        if withrb:
            note.append(f"{withrb} have Rigidbody")
        if withcol:
            note.append(f"{withcol} have colliders")
        if not note:
            note.append("no physics — visual only")
        lines.append(f"| `{arch}` | {len(rs)} | `{top}` | {'; '.join(note)} |")
    lines += ["", "## Reading this table", "",
              "The *typical* column is the most common component stack in that family.",
              "Individual objects vary — always confirm the object's own row in",
              "`ASSET-INDEX.tsv` (`components` column) before building the prefab.", "",
              "**A family listed as 'no physics — visual only' must not receive**",
              "**colliders.** Adding them changes behaviour and costs frame time for",
              "nothing."]
    p = os.path.join(out, "COMPONENT-RECIPES.md")
    open(p, "w").write("\n".join(lines))
    return p


def write_claude_section(out, project, docs_rel, rows):
    txt = f"""<!-- paste this into CLAUDE.md -->

## Assets — resolve, never invent

**Every visual in this game already exists in the extraction.** {len(rows)} objects
are catalogued. If you cannot find one, the lookup failed — the asset did not.

Before putting anything on screen:

```
grep -i '<word>' {docs_rel}/ASSET-INDEX.tsv
```

| Need | Read |
|---|---|
| "where is X / does X exist" | `{docs_rel}/ASSET-INDEX.tsv` (grep first, always) |
| "what is X made of, which components" | `{docs_rel}/ASSET-CATALOG.md` |
| "how do these pieces combine" | `{docs_rel}/COMPOSITION-RULES.md` |
| "which components for this kind of object" | `{docs_rel}/COMPONENT-RECIPES.md` |
| "I think the asset is missing" | `{docs_rel}/ASSET-RULES.md` — run the 5-step protocol before drawing |

**Hard rules**
- Do not draw a mesh, sprite or effect before running the 5-step protocol in `ASSET-RULES.md`.
- `grep -c '^g ' x.obj` before loading any OBJ — multi-group OBJs load as a fragment.
- Multi-slot renderers need one material per slot, in order.
- Do not guess a constant that is measurable in the extraction.
"""
    p = os.path.join(out, "CLAUDE-SECTION.md")
    open(p, "w").write(txt)
    return p


def write_composition(rows, out, project, game_dir):
    multi = sorted([r for r in rows if any(g > 1 for g in r["groups"].values())],
                   key=lambda r: -max(r["groups"].values() or [0]))
    composite = sorted([r for r in rows if len(r["children"]) >= 3],
                       key=lambda r: -len(r["children"]))
    multislot = sorted([r for r in rows if len(r["mat_slots"]) > 1],
                       key=lambda r: -len(r["mat_slots"]))
    multimesh = sorted([r for r in rows if len(r["meshes"]) > 1],
                       key=lambda r: -len(r["meshes"]))
    L = [f"# Composition Rules — {project}", "",
         "> How separate files become one object on screen. This is the file that",
         "> answers *\"I found three OBJs and five materials — now what?\"*", ""]

    withnodes = [r for r in rows if r["nodes"]]
    if withnodes:
        L += ["## 0. The node tree — read this before anything else", "",
              f"{len(withnodes)} of {len(rows)} objects carry `nodes` in their",
              "`entity.json`: the object's **real hierarchy**, one entry per GameObject",
              "with its `parent`, `localPosition/Rotation/Scale`, the `mesh_file` it",
              "carries, its `materials` **in slot order**, `active`, and `fracture`.", "",
              "**Build from `nodes`. The flat `meshes` list below is an index, not a",
              "recipe.** A folder of OBJs cannot say which one is the body, which is a",
              "plank and which is debris — the tree can.", "",
              "```bash",
              "# the tree of one object",
              "python3 -c \"import json;n=json.load(open('<entity>/entity.json'))['nodes'];"
              "[print('  '*x['depth']+x['name'], x.get('mesh_file') or '', x.get('materials') or '',"
              " 'FRAC' if x.get('fracture') else '') for x in n]\"",
              "```", "",
              "| object | nodes | mesh nodes | fracture |", "|---|---|---|---|"]
        for r in sorted(withnodes, key=lambda r: -len(r["nodes"]))[:20]:
            L.append(f"| `{r['name']}` | {len(r['nodes'])} | "
                     f"{sum(1 for n in r['nodes'] if n.get('mesh_file'))} | "
                     f"{sum(1 for n in r['nodes'] if n.get('fracture'))} |")
        L += ["",
              "**Fracture nodes are the break state.** Parent them under a disabled root;",
              "they are not part of the intact object. Detection is structural — the node's",
              "own name or an ancestor matching `break|crack|debris|shatter`.", ""]

    L += ["## 1. One object, many meshes", "",
          f"{len(multimesh)} objects are assembled from more than one OBJ. The mesh list",
          "in the catalog is the **parts list**, in order.", "",
          "| object | meshes |", "|---|---|"]
    for r in multimesh[:25]:
        L.append(f"| `{r['name']}` | {len(r['meshes'])} — " +
                 ", ".join(f"`{m}`" for m in r["meshes"][:6]) +
                 (" …" if len(r["meshes"]) > 6 else "") + " |")

    nfiles = sum(1 for r in rows for g in r["groups"].values() if g > 1)
    L += ["", "## 2. One OBJ, many groups  ← the most common failure", "",
          f"**{len(multi)} objects** own **{nfiles} OBJ files** that contain more than one",
          "`g ` group. Unity's",
          "`LoadAssetAtPath` returns **only the first**. Symptom: \"I loaded the mesh but",
          "half of it is missing\" → then someone draws the missing half by hand.", "",
          "| object | file | groups |", "|---|---|---|"]
    for r in multi[:25]:
        for m, g in r["groups"].items():
            if g > 1:
                L.append(f"| `{r['name']}` | `{m}` | **{g}** |")

    L += ["", "## 3. One renderer, many material slots", "",
          f"{len(multislot)} objects have more than one material slot. **Slot order maps to",
          "sub-mesh order.** Assigning a single material paints the whole object.", "",
          "| object | slots |", "|---|---|"]
    for r in multislot[:25]:
        L.append(f"| `{r['name']}` | {len(r['mat_slots'])} — " +
                 ", ".join(f"`{m}`" for m in r["mat_slots"][:8]) +
                 (" …" if len(r["mat_slots"]) > 8 else "") + " |")

    L += ["", "## 4. Composites — rebuild the hierarchy, do not flatten", "",
          f"{len(composite)} objects have 3+ children. The child list is the prefab tree;",
          "child names carry meaning (attach points, pose variants, renderer setters).", "",
          "| object | children |", "|---|---|"]
    for r in composite[:25]:
        L.append(f"| `{r['name']}` | {len(r['children'])} — " +
                 ", ".join(f"`{c}`" for c in r["children"][:8]) +
                 (" …" if len(r["children"]) > 8 else "") + " |")

    L += ["", "## 5. Where the truth lives", "",
          "| question | source |", "|---|---|",
          f"| what is this object's real place in the scene | `{os.path.abspath(game_dir)}/scenes/*.tree.txt` |",
          f"| every float/colour/keyword of a surface | `{os.path.abspath(game_dir)}/materials.json` |",
          f"| pivot, PPU, 9-slice of a sprite | `{os.path.abspath(game_dir)}/sprite-meta.json` |",
          f"| engine constants | `{os.path.abspath(game_dir)}/project-settings/` |",
          "",
          "**Combined meshes.** Some extractions contain a single mesh that already holds",
          "several parts in their correct relative positions (a `Combined Mesh` / `Mesh",
          "Combiner` output). When one exists, use it instead of positioning parts by hand —",
          "hand-placement is what makes a rebuild look hand-made."]
    p = os.path.join(out, "COMPOSITION-RULES.md")
    open(p, "w").write("\n".join(L))
    return p


# --------------------------------------------------------------------------- #

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("extracted")
    ap.add_argument("--out", required=True)
    ap.add_argument("--project-name", default=None)
    a = ap.parse_args()

    game_dir, fname, layout = find_layout(a.extracted)
    project = a.project_name or os.path.basename(a.extracted.rstrip("/"))
    os.makedirs(a.out, exist_ok=True)

    ents = load_entities(game_dir, fname)
    rows = []
    for e in ents:
        n = norm(e, game_dir)
        groups = {}
        for m in n["meshes"]:
            fp = os.path.join(game_dir, n["dir"], m)
            if not os.path.isfile(fp):
                fp = os.path.join(game_dir, "meshes", m)
            g = obj_groups(fp)
            if g:
                groups[m] = g
        arch = archetype_of(n["name"])
        rows.append({
            **n,
            "groups": groups,
            "archetype": arch,
            "aliases": aliases_of(n["name"], arch),
            "recipe": recipe_of(n),
            "sprites_flag": bool(n["sprites"]),
        })

    docs_rel = a.out.replace("\\", "/")
    made = [
        write_index(rows, a.out),
        write_composition(rows, a.out, project, game_dir),
        write_recipes(rows, a.out, project),
        write_rules(a.out, project, game_dir, rows, layout),
    ]
    print(f"layout={layout}  entities={len(rows)}")
    for m in made:
        print("  wrote", m, f"({os.path.getsize(m)}B)")


if __name__ == "__main__":
    main()
