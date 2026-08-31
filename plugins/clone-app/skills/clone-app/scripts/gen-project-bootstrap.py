#!/usr/bin/env python3
"""Write the clone project's day-one instructions, measured from the extraction.

    python3 gen-project-bootstrap.py <workdir> --out <dir> [--project-name NAME]

Emits:
    CLAUDE.md    the clone repo's root instructions (Tier 1 — always in context)
    INSTALL.md   where each file goes in the new repo

Why this exists: the build session starts with an empty repo and a 700 MB
extraction it has never seen. Told nothing, it invents assets. This file is the
routing table that makes the extraction reachable — generated, so its numbers are
measured rather than remembered, and no human has to write a hand-off prompt.
"""

import argparse
import glob
import json
import os
import sys


def count(d, pat="*"):
    return len(glob.glob(os.path.join(d, pat))) if os.path.isdir(d) else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workdir")
    ap.add_argument("--out", required=True)
    ap.add_argument("--project-name", default="the clone")
    a = ap.parse_args()

    W = os.path.abspath(a.workdir)
    E = os.path.join(W, "extracted")
    G = os.path.join(E, "game-assets")
    AG = os.path.join(E, "asset-guide")
    if not os.path.isdir(E):
        sys.exit(f"no extracted/ under {W}")
    os.makedirs(a.out, exist_ok=True)
    name = a.project_name

    # --- measure -------------------------------------------------------- #
    ents = sorted(glob.glob(os.path.join(G, "entities", "*", "entity.json")))
    nodes_cov = mesh_nodes = frac_nodes = 0
    for f in ents:
        try:
            n = json.load(open(f)).get("nodes") or []
        except Exception:
            continue
        if n:
            nodes_cov += 1
            mesh_nodes += sum(1 for x in n if x.get("mesh_file"))
            frac_nodes += sum(1 for x in n if x.get("fracture"))
    ui = count(os.path.join(G, "ui"), "*.json")
    sprites = count(os.path.join(G, "sprites"), "*.png")
    meshes = count(os.path.join(G, "meshes"), "*.obj")
    levels = len(glob.glob(os.path.join(G, "levels", "**", "*.json"), recursive=True))
    has_guide = os.path.isdir(AG)

    engine = "Unity"
    settings = os.path.join(G, "project-settings", "README.md")
    engine_note = ""
    if os.path.isfile(settings):
        engine_note = ("Measured engine settings are in "
                       "`$W/extracted/game-assets/project-settings/` — apply them "
                       "**before writing gameplay code**, they are not defaults.")

    # --- CLAUDE.md ------------------------------------------------------ #
    C = [f"# {name}", "",
         f"Local, technical-verification rebuild. No distribution, no store, no",
         f"commercial use; extracted art is reference material.", "",
         "## The extraction",
         "", "```bash", f"W={W}", "```", "",
         f"{len(ents)} entities · {ui} UI canvases · {sprites} sprites · {meshes} meshes"
         + (f" · {levels} levels" if levels else ""), "", "---", "",
         "## Read first", "",
         "| File | For |", "|---|---|"]

    if has_guide:
        C += [
            "| **`Docs/assets/ASSET-INDEX.tsv`** | **One line per asset — grep this BEFORE putting anything on screen.** name, archetype, meshes, OBJ group counts, material slots, textures, components, children, **node counts + node→mesh map**, aliases. |",
            "| **`Docs/assets/UI-ROLE-GUIDE.md`** | **Where a UI element sits and what it is for.** Recurring elements with their measured screen zone, size and sprite candidates. |",
            "| `Docs/assets/UI-ELEMENT-INDEX.tsv` | Every UI node: canvas, node, zone, size, depth, components, sprite candidates, path. Grep it. |",
            "| `Docs/assets/COMPOSITION-RULES.md` | **How pieces combine** — §0 the node tree, multi-mesh objects, multi-group OBJs, multi-slot renderers, composites. |",
            "| `Docs/assets/COMPONENT-RECIPES.md` | Archetype → the Unity components it actually needs. |",
            "| `Docs/assets/ASSET-RULES.md` | The 5-step asset-resolution protocol + prohibitions. **Read before claiming an asset is missing.** |",
            "| `Docs/REFERENCE-SOURCES.md` | What is in the extraction and **the command that opens each part**. |",
        ]
    C += ["| `Docs/reconstruction/` | Architecture, mechanics, runtime flow, meta/LiveOps, unknowns, C# skeleton (when the target is a game). |",
          "| `Docs/clone-build-spec.md` | The build contract. |", ""]

    C += ["## Working rules", "",
          "### Never invent an asset",
          "",
          "Every visual already exists in the extraction. If you cannot find one, the",
          "**lookup** failed — the asset did not. In order, stop at the first hit:",
          "", "```bash",
          "grep -i '<word>' Docs/assets/ASSET-INDEX.tsv          # 1. the asset",
          "grep -i '<word>' Docs/assets/UI-ELEMENT-INDEX.tsv     # 1b. if it is UI",
          "grep -i '<word>' $W/extracted/game-assets/scenes/*.tree.txt   # 2. scene node name",
          "ls $W/extracted/game-assets/sprites | grep -i '<word>'        # 3. sprite",
          "```", "",
          "Try synonyms (slot/tray/carrier, arrow/chevron, rail/track/conveyor).",
          "Still nothing → **write down why before you draw.** Full protocol:",
          "`Docs/assets/ASSET-RULES.md`.", ""]

    if nodes_cov:
        C += ["### Build objects from the node tree", "",
              f"{nodes_cov}/{len(ents)} entities carry `nodes` in `entity.json` — the object's",
              f"real hierarchy ({mesh_nodes} mesh-bearing nodes, {frac_nodes} fracture nodes).",
              "Each node has `parent`, `localPosition/Rotation/Scale`, `mesh_file`,",
              "`materials` (**in slot order**), `active`, `fracture`.", "",
              "```bash",
              "python3 -c \"import json;n=json.load(open('<entity>/entity.json'))['nodes'];"
              "[print('  '*x['depth']+x['name'], x.get('mesh_file') or '', x.get('materials') or '',"
              " 'FRAC' if x.get('fracture') else '') for x in n]\"",
              "```", "",
              "- Apply each node's local transform. **Parts stacked at the origin means this was skipped.**",
              "- Assign `materials` in order to `sharedMaterials`. One material on a multi-slot renderer paints the whole object.",
              "- Parent `fracture` nodes under a disabled root — that is the break state, not the object.",
              "- The flat `whole_mesh_files` list is a lookup index, **not** a recipe.", ""]

    C += ["### Three checks on every piece", "",
          "1. Look at `preview.png` in the entity folder — names lie, renders do not.",
          "2. `grep -c '^g ' x.obj` — more than one group means `LoadAssetAtPath` hands you a fragment.",
          "3. Read the material's floats in `materials.json` before calling a surface wrong.", ""]

    if ui:
        C += ["### UI", "",
              "Node name, screen zone and size are **measured fact** (from RectTransform",
              "anchors). **Sprite candidates are guesses** — the canvas dump collapses",
              "`Image` to `CanvasRenderer` and loses the binding, so they were matched by",
              "name. Open the PNG before using one. A control is often plate + icon +",
              "hitbox, not one sprite.", "",
              "```bash",
              "awk -F'\\t' -v c='<Canvas>' '$1==c{printf \"%*s%s  [%s %s]\\n\", $5*2, \"\", $2, $3, $4}' \\",
              "  Docs/assets/UI-ELEMENT-INDEX.tsv",
              "```", ""]

    if engine_note:
        C += ["### Engine settings", "", engine_note, ""]

    C += ["### Evidence discipline", "",
          "The reconstruction tags every claim: **[D]** measured · **[S]** certain from a",
          "signature · **[I]** inferred · **[X]** not recoverable. Keep the tags when you",
          "carry a claim into code. Do not promote a guess to a fact, and do not invent a",
          "number that is measurable in the extraction — say \"not measured\" instead.", "",
          "### Generated vs curated", "",
          "`Docs/assets/` and `Docs/REFERENCE-SOURCES.md` are **generated** — do not hand-edit,",
          "they are overwritten on the next extraction. Hard-won findings go in a separate",
          "`Docs/ASSET-MAP.md` that you own.", "",
          "```bash",
          "# regenerate after a re-extraction",
          "python3 <clone-app>/scripts/gen-asset-guide.py       $W/extracted --out Docs/assets",
          "python3 <clone-app>/scripts/gen-ui-map.py            $W/extracted --out Docs/assets",
          "python3 <clone-app>/scripts/gen-reference-sources.py $W --out Docs/REFERENCE-SOURCES.md",
          "```", ""]
    open(os.path.join(a.out, "CLAUDE.md"), "w").write("\n".join(C))

    # --- INSTALL.md ----------------------------------------------------- #
    I = [f"# Bootstrap install — {name}", "",
         "Where each generated file goes in the clone repo. clone-build's P1 does this;",
         "these are the same steps by hand.", "",
         "```bash", f"W={W}", "REPO=<the clone repo>", "",
         "cp $W/deliverables/bootstrap/CLAUDE.md         $REPO/CLAUDE.md",
         "mkdir -p $REPO/Docs/assets",
         "cp $W/extracted/asset-guide/*                  $REPO/Docs/assets/",
         "cp $W/extracted/REFERENCE-SOURCES.md           $REPO/Docs/",
         "cp $W/deliverables/clone-build-spec.md         $REPO/Docs/",
         "cp -R $W/deliverables/reconstruction           $REPO/Docs/reconstruction   # game targets",
         "```", "",
         "## What NOT to copy", "",
         "- `extracted/game-assets/` — leave it outside the repo and reference `$W`.",
         "  It is hundreds of MB of reference material, and it is not yours to ship.",
         "- `raw/` — regenerable; delete with `clean-workdir.sh` when finished.", "",
         "## Importing the art", "",
         "`$W/extracted/game-assets/unity-import/ImportExtracted.cs` rebuilds each entity",
         "as a prefab **from its node tree**: hierarchy, local transforms, one material per",
         "slot, and fracture debris under a disabled `Broken` root. Drop it in",
         "`Assets/Editor/` and run **Tools → Clone App → Import Extracted Assets**.",
         "",
         "If the project already has its own import pipeline, take `BuildFromNodes()` and",
         "`ResolveNamedMaterial()` from that file rather than replacing the pipeline.", ""]
    open(os.path.join(a.out, "INSTALL.md"), "w").write("\n".join(I))

    print(f"entities={len(ents)} nodes={nodes_cov} ui={ui} guide={'yes' if has_guide else 'no'}")
    for f in ("CLAUDE.md", "INSTALL.md"):
        p = os.path.join(a.out, f)
        print("  wrote", p, f"({os.path.getsize(p)}B)")


if __name__ == "__main__":
    main()
