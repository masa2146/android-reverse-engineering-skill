#!/usr/bin/env python3
"""Generate REFERENCE-SOURCES.md — what exists in the extraction, and how to reach it.

    python3 gen-reference-sources.py <workdir> --out <file.md> [--lang tr|en]

<workdir> is the clone-app working directory (the one holding extracted/, raw/,
deliverables/). Every count and size here is **measured at generation time**, so
the numbers cannot drift the way a hand-written inventory does.

The point of this file: an AI that does not know a source exists cannot consult
it. Every row therefore carries a concrete command that reaches the data, not
just a path.
"""

import argparse
import json
import os
import sys
from collections import Counter

# what each known directory is for, and the command that opens it
KNOWN = {
    "game-assets/entities":        ("Per-object packages: `.obj` + `.mtl` + `preview.png` + `entity.json`",
                                    "ls '{p}' | head; open '{p}/<Name>/preview.png'"),
    "game-assets/meshes":          ("Raw meshes with no entity of their own", "ls '{p}' | head"),
    "game-assets/textures":        ("Source textures (PNG)", "ls '{p}' | head"),
    "game-assets/sprites":         ("Cropped sprites — UI and 2D art", "ls '{p}' | grep -i <word>"),
    "game-assets/particles":       ("Particle system dumps, module by module", "ls '{p}' | head"),
    "game-assets/audio":           ("PCM WAV, import as-is", "ls '{p}' | head"),
    "game-assets/fonts":           ("Real TTF/OTF — regenerate TMP SDF from these", "ls '{p}'"),
    "game-assets/ui":              ("Canvas dumps: full RectTransform trees per screen",
                                    "python3 -c \"import json;d=json.load(open('{p}/<Canvas>.json'));print(json.dumps(d['tree'],indent=1)[:2000])\""),
    "game-assets/scenes":          ("Real scene hierarchies (`*.tree.txt`) + lights/cameras (`*.objects.json`)",
                                    "grep -i <word> '{p}'/*.tree.txt"),
    "game-assets/levels":          ("Level data as shipped/downloaded", "ls '{p}' | head"),
    "game-assets/project-settings": ("Measured engine settings — physics, time, quality, layers", "ls '{p}'"),
    "game-assets/shaders":         ("Shader interfaces + full property tables", "ls '{p}'"),
    "game-assets/spine":           ("Spine 2D skeletal data", "ls '{p}' | head"),
    "game-assets/text":            ("Shipped TextAssets (IAP catalog, remote-config fallback)", "ls '{p}'"),
    "game-assets/unity-import":    ("Ready-made Unity editor importer", "cat '{p}/README.md'"),
    "store/screenshots":           ("Store screenshots — visual ground truth", "open '{p}'/01.png"),
    "deliverables/reconstruction": ("The buildable design: architecture, mechanics, flow, meta, unknowns, C# skeleton",
                                    "cat '{p}/README.md'"),
    "deliverables/asset-guide":    ("Generated asset-usage guide — index, composition, recipes, UI roles",
                                    "grep -i <word> '{p}'/ASSET-INDEX.tsv"),
    "raw/decompiled":              ("jadx sources (Java layer only for a Unity title)", "grep -rl <word> '{p}/sources' | head"),
    "raw/package":                 ("The downloaded package", "ls '{p}'"),
    "raw/unity-work/merged":       ("**The game's own asset bundle.** Ordered/relational data (ScriptableObject "
                                    "contents, PPtr order) survives ONLY here — the extraction flattens it.",
                                    "ls '{p}'"),
    "raw/unity-work/meta":         ("`global-metadata.dat` — retained for a later Il2CppInspector pass", "ls -la '{p}'"),
    "reverse/apk":                 ("Split APKs", "ls '{p}'"),
    "reverse/cdn":                 ("CDN capture work: requests, download scripts, extracted levels", "ls '{p}'"),
    "reverse/il2cpp":              ("IL2CPP artefacts", "ls '{p}'"),
    "reverse/addressables":        ("Addressable bundles pulled from the CDN", "ls '{p}' | head"),
}

# single files worth naming
KNOWN_FILES = {
    "extracted/api-surface.md":     "Every type/method/property name. **Never open whole — grep it.**",
    "extracted/api-surface.json":   "Same, machine form. **Ignore every `fields` array** (misaligned for metadata v31); methods and properties are correct.",
    "extracted/mechanics-digest.md": "Core loop, fail states, mechanic catalog, powerups, economy",
    "extracted/logic-digest.md":    "In-app systems, signature-tagged",
    "extracted/unity-digest.md":    "Engine, rendering, scene graph, entity taxonomy, code architecture",
    "extracted/re-digest.md":       "Reverse-engineering record",
    "extracted/re-summary.txt":     "The 5 KB authoritative summary — read this first",
    "extracted/payloads.json":      "Endpoint contracts + the real IAP catalog",
    "extracted/backend-recon.md":   "Backend rebuild target",
    "extracted/netcode-recon.md":   "Host/transport inventory",
    "extracted/nav-graph.json":     "Screen graph, provenance-tagged",
    "extracted/design-tokens.json": "Design tokens (Java-side; for a Unity title this is SDK noise — use game-assets/)",
    "extracted/coverage-report.md": "The honest gaps in the extraction",
    "extracted/game-assets/manifest.json":  "Extraction manifest — counts and notes",
    "extracted/game-assets/materials.json": "Every float/colour/keyword of every material",
    "extracted/game-assets/physics.json":   "Physic materials + rigidbodies",
    "extracted/game-assets/sprite-meta.json": "Pivot, pixels-per-unit, **9-slice borders** — required for UI",
    "extracted/game-assets/IMPORT.md":      "Import rules and the importer flags you must set by hand",
    "extracted/game-assets/ARCHITECTURE.md": "Class inventory by assembly + namespace",
}

SKIP_DIRS = {".git", "__pycache__", "node_modules"}


def human(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f}{u}" if u == "B" else f"{n:.1f}{u}"
        n /= 1024.0
    return f"{n:.1f}TB"


def scan(d):
    """(file count, total bytes, extension counter) for a directory tree."""
    n = 0
    size = 0
    ext = Counter()
    for root, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in files:
            p = os.path.join(root, f)
            try:
                size += os.path.getsize(p)
            except OSError:
                continue
            n += 1
            ext[os.path.splitext(f)[1].lower() or "(none)"] += 1
    return n, size, ext


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workdir")
    ap.add_argument("--out", required=True)
    ap.add_argument("--project-name", default=None)
    a = ap.parse_args()

    W = os.path.abspath(a.workdir)
    if not os.path.isdir(W):
        sys.exit(f"not a directory: {W}")
    name = a.project_name or os.path.basename(W)

    L = [f"# Reference sources — {name}", "",
         "> **Generated.** Every count and size below was measured when this file was",
         "> written, so it cannot drift the way a hand-kept inventory does. Regenerate",
         "> after any re-extraction:",
         ">",
         "> ```",
         f"> python3 gen-reference-sources.py {W} --out <this file>",
         "> ```",
         "",
         "> Rule: **before deciding anything about art, mechanics or data schema, read the",
         "> source.** Every row carries the command that reaches it — a source you cannot",
         "> open is a source you will guess instead.", "",
         f"Root (outside the project, not in version control):", "",
         "```", W, "```", ""]

    # package identity, if we can find it
    play = os.path.join(W, "extracted", "store", "play.json")
    if os.path.isfile(play):
        try:
            d = json.load(open(play))
            L += [f"Game: **{d.get('title')}** `{d.get('package')}` {d.get('version') or ''} · "
                  f"{d.get('developer')} · {d.get('rating',0):.2f}★ / "
                  f"{d.get('rating_count','?')} · {d.get('installs','?')}", ""]
        except Exception:
            pass

    L += ["---", "", "## 1. Directories — what is inside, how to open it", "",
          "Set this once, then every command below works verbatim:", "",
          "```bash", f"W={W}", "```", "",
          "| path | what | files | size | how to reach it |", "|---|---|---|---|---|"]

    seen = set()
    for rel, (what, cmd) in KNOWN.items():
        for base in ("extracted", "", "raw", "deliverables", "reverse"):
            p = os.path.join(W, base, rel) if base else os.path.join(W, rel)
            p = os.path.normpath(p)
            if p in seen or not os.path.isdir(p):
                continue
            seen.add(p)
            n, size, ext = scan(p)
            if n == 0:
                continue
            shown = os.path.relpath(p, W)
            L.append(f"| `{shown}/` | {what} | {n} | {human(size)} | `{cmd.format(p='$W/'+shown)}` |")
            break

    # anything else at the top two levels we did not name
    L += ["", "### Other directories present", ""]
    others = []
    for base in ("extracted", "raw", "deliverables", "reverse"):
        bp = os.path.join(W, base)
        if not os.path.isdir(bp):
            continue
        for sub in sorted(os.listdir(bp)):
            p = os.path.join(bp, sub)
            if not os.path.isdir(p) or p in seen:
                continue
            if any(q.startswith(p + os.sep) for q in seen):
                continue  # a parent of something already listed
            n, size, _ = scan(p)
            if n:
                others.append(f"- `{os.path.relpath(p, W)}/` — {n} files, {human(size)}")
    L += others or ["_(none)_"]

    L += ["", "---", "", "## 2. Key files", "",
          "| file | what | size |", "|---|---|---|"]
    for rel, what in KNOWN_FILES.items():
        p = os.path.join(W, rel)
        if os.path.isfile(p):
            L.append(f"| `{rel}` | {what} | {human(os.path.getsize(p))} |")

    # reconstruction docs
    rec = os.path.join(W, "deliverables", "reconstruction")
    if os.path.isdir(rec):
        L += ["", "### `deliverables/reconstruction/`", "",
              "| file | lines |", "|---|---|"]
        for f in sorted(os.listdir(rec)):
            p = os.path.join(rec, f)
            if os.path.isfile(p) and f.endswith(".md"):
                L.append(f"| `{f}` | {sum(1 for _ in open(p, errors='ignore'))} |")
        code = os.path.join(rec, "code")
        if os.path.isdir(code):
            tot = sum(sum(1 for _ in open(os.path.join(code, f), errors="ignore"))
                      for f in os.listdir(code) if f.endswith((".cs", ".md")))
            L.append(f"| `code/` ({len(os.listdir(code))} files) | {tot} |")
        L += ["",
              "Evidence tags used throughout: **[D]** measured · **[S]** certain from a",
              "signature · **[I]** inferred · **[X]** not recoverable."]

    # what is NOT here
    L += ["", "---", "", "## 3. What is NOT here", ""]
    missing = []
    for rel, why in (
        ("raw", "the raw layer was cleaned — re-download before any deeper RE pass"),
        ("extracted/game-assets/ui", "no canvas dump: this extraction predates the UI dumper, "
                                     "or the bundle had no Canvas objects. Re-run `unity-assets.sh` to produce it."),
        ("extracted/game-assets/levels", "no level data shipped in the package — levels are served at runtime"),
    ):
        if not os.path.exists(os.path.join(W, rel)):
            missing.append(f"- `{rel}` — {why}")
    L += missing or ["_Everything expected is present._"]

    L += ["", "---", "", "## 4. Recipes — the questions that actually get asked", "",
          "```bash",
          f"W={W}", "E=$W/extracted", "",
          "# does this asset exist, and what is it made of",
          "grep -i '<word>' $E/asset-guide/ASSET-INDEX.tsv",
          "",
          "# where does this UI element sit, how big, which sprite",
          "grep -i '<word>' $E/asset-guide/UI-ELEMENT-INDEX.tsv",
          "",
          "# rebuild one canvas' tree",
          "awk -F'\\t' -v c='<Canvas>' '$1==c{printf \"%*s%s  [%s %s]\\n\", $5*2, \"\", $2, $3, $4}' \\",
          "  $E/asset-guide/UI-ELEMENT-INDEX.tsv",
          "",
          "# what is this object's real place in the scene",
          "grep -i '<word>' $E/game-assets/scenes/*.tree.txt",
          "",
          "# every value of a material",
          "python3 -c \"import json,sys;d=json.load(open('$E/game-assets/materials.json'));"
          "print(json.dumps(d['<Material>'],indent=1))\"",
          "",
          "# how many groups does this OBJ have (>1 loads as a fragment)",
          "grep -c '^g ' <file>.obj",
          "",
          "# does a class with this name exist, what are its methods",
          "grep -n -A3 '#### `<Type>`' $E/api-surface.md",
          "```", ""]

    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    open(a.out, "w").write("\n".join(L))
    print("wrote", a.out, f"({os.path.getsize(a.out)}B)")


if __name__ == "__main__":
    main()
