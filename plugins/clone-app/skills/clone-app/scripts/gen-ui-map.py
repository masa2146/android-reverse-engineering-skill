#!/usr/bin/env python3
"""Generate the UI usage map: where each element sits on screen and what it is for.

    python3 gen-ui-map.py <extracted-dir> --out <docs-dir>

Answers the question the asset catalog cannot:
    "the X in the top-right of a modal — which sprite is it, what is it for?"

Emits:
    UI-ROLE-GUIDE.md       recurring element roles: what/where/which sprites   <- read this first
    UI-ELEMENT-INDEX.tsv   greppable: canvas, node path, zone, size, sprite candidates

A per-canvas tree is NOT emitted as a second file — it is one awk line off the
index, and a generated file that only re-renders another generated file is a file
that goes stale. The recipe is printed in UI-ROLE-GUIDE.md.

Note on a real extraction gap: the canvas dump keeps RectTransform trees and
component *names*, but `Image` components collapse to `CanvasRenderer` and the
sprite binding is lost. So sprites are matched to nodes by **name token overlap**
and reported as CANDIDATES, ranked — never as fact. The node name, the screen
zone and the size are facts; the sprite is a ranked guess you confirm by opening
the PNG.
"""

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict

STOP = {"image", "bg", "parent", "content", "pivot", "root", "container",
        "group", "holder", "obj", "go", "new", "the", "view", "panel"}


# --------------------------------------------------------------------------- #

def find_game_dir(extracted):
    for cand in (os.path.join(extracted, "game-assets"),
                 os.path.join(extracted, "game-assets-legacy", "assets")):
        if os.path.isdir(cand):
            return cand
    sys.exit(f"no game-assets under {extracted}")


def toks(s):
    out = []
    for p in re.split(r"[^A-Za-z0-9]+", s):
        for piece in re.findall(r"[A-Z]?[a-z]+|\d+|[A-Z]+(?![a-z])", p):
            t = piece.lower()
            if len(t) > 2 and not t.isdigit():
                out.append(t)
    return out


def zone_of(rect):
    """Screen zone from the anchor pair. This part is fact, not inference."""
    if not rect:
        return "?"
    a0 = rect.get("anchorMin") or [0, 0]
    a1 = rect.get("anchorMax") or [0, 0]
    sx = abs(a1[0] - a0[0]) > 0.01
    sy = abs(a1[1] - a0[1]) > 0.01
    if sx and sy:
        return "full-stretch"
    cx = (a0[0] + a1[0]) / 2.0
    cy = (a0[1] + a1[1]) / 2.0
    hx = "left" if cx < 0.34 else ("right" if cx > 0.66 else "center")
    vy = "bottom" if cy < 0.34 else ("top" if cy > 0.66 else "middle")
    if sx:
        return f"stretch-x @{vy}"
    if sy:
        return f"stretch-y @{hx}"
    if hx == "center" and vy == "middle":
        return "center"
    return f"{vy}-{hx}"


def size_of(rect):
    if not rect:
        return ""
    sd = rect.get("sizeDelta") or [0, 0]
    if sd[0] or sd[1]:
        return f"{sd[0]:g}x{sd[1]:g}"
    return "(stretched)"


# --------------------------------------------------------------------------- #

def load_sprites(game_dir):
    d = os.path.join(game_dir, "sprites")
    if not os.path.isdir(d):
        return []
    return [os.path.splitext(f)[0] for f in sorted(os.listdir(d))
            if f.lower().endswith(".png")]


def match_sprites(node_name, sprite_toks, limit=4):
    nt = set(toks(node_name)) - STOP
    if not nt:
        return []
    scored = []
    for name, st in sprite_toks:
        ov = nt & st
        if not ov:
            continue
        score = len(ov) / max(1, len(nt | st) ** 0.5)
        scored.append((score, len(ov), name))
    scored.sort(reverse=True)
    return [n for _, _, n in scored[:limit]]


# --------------------------------------------------------------------------- #

def walk(node, path, depth, out):
    rect = node.get("rect")
    out.append({
        "name": node.get("name", "?"),
        "path": path,
        "depth": depth,
        "zone": zone_of(rect),
        "size": size_of(rect),
        "components": node.get("components", []),
    })
    for ch in node.get("children", []) or []:
        walk(ch, f"{path}/{ch.get('name','?')}", depth + 1, out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("extracted")
    ap.add_argument("--out", required=True)
    ap.add_argument("--project-name", default="project")
    a = ap.parse_args()

    game_dir = find_game_dir(a.extracted)
    ui_dir = os.path.join(game_dir, "ui")
    os.makedirs(a.out, exist_ok=True)

    if not os.path.isdir(ui_dir):
        p = os.path.join(a.out, "UI-ROLE-GUIDE.md")
        alt = os.path.join(game_dir, "scene-hierarchy.txt")
        open(p, "w").write(
            f"# UI Role Guide — {a.project_name}\n\n"
            "**This extraction has no `ui/` canvas dump.**\n\n"
            f"The screen hierarchy source for this project is "
            f"`{os.path.abspath(alt)}` — read that instead. "
            "Node names there carry the same semantics (`Close Button`, `Popup Bg`, "
            "`Header Frame`), but anchors and sizes are not recorded, so screen "
            "position must be read off the store screenshots.\n")
        print("no ui/ — wrote pointer only:", p)
        return

    sprites = load_sprites(game_dir)
    sprite_toks = [(s, set(toks(s)) - STOP) for s in sprites]

    canvases = []
    for f in sorted(os.listdir(ui_dir)):
        if not f.endswith(".json"):
            continue
        try:
            d = json.load(open(os.path.join(ui_dir, f)))
        except Exception:
            continue
        nodes = []
        walk(d.get("tree", {}), d.get("tree", {}).get("name", "?"), 0, nodes)
        canvases.append({
            "file": f,
            "name": d.get("name", os.path.splitext(f)[0]),
            "sorting_order": d.get("sorting_order"),
            "nodes": nodes,
            "scripts": sorted({c for n in nodes for c in n["components"]
                               if c.startswith("MB:")}),
        })

    # ---------------- role guide -------------------------------------------- #
    role = defaultdict(lambda: {"n": 0, "zones": Counter(), "sizes": Counter(),
                                "canvases": set()})
    for c in canvases:
        for n in c["nodes"]:
            r = role[n["name"]]
            r["n"] += 1
            r["zones"][n["zone"]] += 1
            if n["size"]:
                r["sizes"][n["size"]] += 1
            r["canvases"].add(c["name"])

    common = sorted(role.items(), key=lambda kv: -kv[1]["n"])
    L = [f"# UI Role Guide — {a.project_name}", "",
         "> **Read this before building any screen.** It answers *where does this",
         "> element sit and what is it for*, which the asset catalog cannot.", "",
         f"{len(canvases)} canvases · {sum(len(c['nodes']) for c in canvases)} nodes · "
         f"{len(sprites)} sprites", "",
         "## How to read a row", "",
         "- **zone** — computed from the RectTransform anchor pair. **This is fact.**",
         "- **typical size** — the most common `sizeDelta`. Fact.",
         "- **sprite candidates** — matched by name-token overlap and ranked.",
         "  **This is a guess.** The canvas dump lost the `Image → sprite` binding",
         "  (Image components collapsed to `CanvasRenderer`). Confirm by opening the",
         "  PNG before you use it.", "",
         "## Recurring elements", "",
         "| element | count | usual zone | typical size | sprite candidates |",
         "|---|---|---|---|---|"]
    for name, r in common[:70]:
        if r["n"] < 3:
            continue
        z = r["zones"].most_common(1)[0][0]
        s = r["sizes"].most_common(1)[0][0] if r["sizes"] else "-"
        cands = match_sprites(name, sprite_toks)
        L.append(f"| `{name}` | {r['n']} | {z} | {s} | " +
                 (", ".join(f"`{x}`" for x in cands) if cands else "—") + " |")

    # pick the close-family node that actually exists in THIS extraction
    close_name = None
    for cand, r in sorted(role.items(), key=lambda kv: -kv[1]["n"]):
        if re.search(r"close|dismiss|\bexit\b|\bquit\b", cand, re.I):
            close_name = cand
            break
    L += ["", f"## Worked example — {close_name or 'the close control'}", ""]
    cb = role.get(close_name) if close_name else None
    if cb:
        zz = ", ".join(f"{z} ({n})" for z, n in cb["zones"].most_common(4))
        ss = ", ".join(f"{s} ({n})" for s, n in cb["sizes"].most_common(3))
        L += [f"`{close_name}` appears in **{cb['n']} canvases**.", "",
              f"- **zones:** {zz}",
              f"- **sizes:** {ss}",
              "- **sprite candidates:** " +
              (", ".join(f"`{x}`" for x in match_sprites(close_name, sprite_toks)) or "—"),
              "- **canvases:** " + ", ".join(f"`{c}`" for c in sorted(cb["canvases"])[:10]) +
              (" …" if len(cb["canvases"]) > 10 else ""),
              "",
              "Close-family sprites in this extraction:", "", "```",
              "\n".join(x for x in sprites
                        if re.search(r"close|cross|dismiss|^x_|_x$", x, re.I))[:1200] or "(none)",
              "```", "",
              "So: a modal's close control is a node named "
              f"`{close_name}`, sitting at the zone above, and its art is one of the sprites "
              "listed. Open the PNG before choosing — the sprite link is a name match, "
              "not a recovered binding.",
              "",
              "Sibling nodes on the same control (grep the index for the canvas to see the",
              "full group — a close button is often plate + icon + hitbox, not one sprite):",
              "", "```bash",
              f"grep -P '\\t{close_name}\\t' UI-ELEMENT-INDEX.tsv | cut -f1,2,3,4",
              "```"]
    else:
        L.append("_No close-family node found in this extraction._")

    L += ["", "## Rebuild one canvas' tree (from the index, no second file needed)", "",
          "```bash",
          "awk -F'\\t' -v c='Popup Canvas' '$1==c{printf \"%*s%s  [%s %s]\\n\", $5*2, \"\", $2, $3, $4}' \\",
          "  Docs/assets/UI-ELEMENT-INDEX.tsv",
          "```",
          "",
          "Columns: 1 canvas · 2 node · 3 zone · 4 size · 5 depth · 6 components ·",
          "7 sprite candidates · 8 full path.", "",
          "## Naming conventions in this extraction", "",
          "Node names are semantic and stable — grep them, do not invent screens:", ""]
    fam = Counter()
    for name, r in role.items():
        t = toks(name)
        if t:
            fam[t[-1]] += r["n"]
    L.append("| trailing token | occurrences | means |")
    L.append("|---|---|---|")
    MEAN = {"button": "an interactive control", "frame": "a 9-sliced border plate",
            "text": "a TMP label", "icon": "a small square glyph",
            "pivot": "an empty transform used as an animation origin",
            "hitbox": "an invisible raycast target — no art",
            "shadow": "a soft blob under an element",
            "arrow": "a directional pointer sprite",
            "image": "a generic sprite host", "area": "a layout region",
            "title": "a header label", "content": "a scroll/layout body"}
    for t, n in fam.most_common(18):
        L.append(f"| `*{t}` | {n} | {MEAN.get(t,'—')} |")

    open(os.path.join(a.out, "UI-ROLE-GUIDE.md"), "w").write("\n".join(L))

    # ---------------- element index ----------------------------------------- #
    p = os.path.join(a.out, "UI-ELEMENT-INDEX.tsv")
    with open(p, "w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["canvas", "node", "zone", "size", "depth",
                    "components", "sprite_candidates", "path"])
        for c in canvases:
            for n in c["nodes"]:
                w.writerow([c["name"], n["name"], n["zone"], n["size"], n["depth"],
                            ";".join(n["components"]),
                            ";".join(match_sprites(n["name"], sprite_toks)),
                            n["path"]])

    print(f"canvases={len(canvases)} nodes={sum(len(c['nodes']) for c in canvases)} "
          f"sprites={len(sprites)}")
    for f in ("UI-ROLE-GUIDE.md", "UI-ELEMENT-INDEX.tsv"):
        fp = os.path.join(a.out, f)
        print("  wrote", fp, f"({os.path.getsize(fp)}B)")


if __name__ == "__main__":
    main()
