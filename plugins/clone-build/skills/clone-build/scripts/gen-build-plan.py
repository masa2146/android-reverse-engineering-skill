#!/usr/bin/env python3
"""Generate build-plan.json (task graph) from a clone-build-spec.md + $WORK artifacts.

Deterministic: no clock, no randomness — same inputs produce identical output.
Branch-agnostic core. Gate KIND is set per task type; gate COMMAND is left empty
here and filled later by the branch build guide.
"""
import argparse, json, os, re, sys

REQUIRED = ["design-tokens.json", "payloads.json", "nav-graph.json"]

# task type -> (gate kind, pass_when)
GATE = {
    "scaffold":    ("build",        "project compiles, 0 errors"),
    "design":      ("build",        "design tokens applied; compiles, 0 errors"),
    "ui":          ("visual-diff",  "screenshot matches target >= threshold; build+launch no crash"),
    "scene":       ("visual-diff",  "scene screenshot matches target; compiles, 0 console errors"),
    "api":         ("tdd",          "contract test vs payloads.json shape exits 0"),
    "logic":       ("tdd",          "failing test written first, then test exits 0"),
    "integration": ("launch-crash", "app/scene launches; no fatal in log for N seconds"),
    # game-branch types. A game is not a screen list — it is engine settings,
    # imported art, mechanics, a level pipeline and a tuning backlog.
    "engine-settings": ("build",       "measured project settings applied; compiles, 0 errors"),
    "art-import":      ("build",       "prefabs built FROM entity.json nodes (hierarchy, local TRS, per-slot materials); count matches the index"),
    "mechanic":        ("tdd",         "failing test written first from the reconstruction's rule, then test exits 0"),
    "level-pipeline":  ("tdd",         "schema round-trips: author -> validate -> content hash -> load -> identical board"),
    "tuning":          ("manual",      "value chosen by the experiment in 05-UNKNOWNS.md and recorded, or explicitly deferred"),
}


def detect_branch(spec_text):
    m = re.search(r'(?im)^.*selected stack.*$', spec_text)
    line = m.group(0).lower() if m else ""
    if "unity" in line or "il2cpp" in line:
        return "game", "unity"
    if "flutter" in line:
        return "app", "flutter"
    if re.search(r'react.?native', line):
        return "app", "react-native"
    if re.search(r'native|kotlin|compose|jetpack', line):
        return "app", "native-android"
    return "app", "unknown"


def field(spec_text, label):
    m = re.search(r'\*\*%s:\*\*\s*([^\n·|]+)' % re.escape(label), spec_text)
    return m.group(1).strip() if m else ""


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def gate(task_type):
    k, pw = GATE[task_type]
    return {"kind": k, "command": "", "pass_when": pw}


def _read(path):
    try:
        with open(path, errors="ignore") as f:
            return f.read()
    except OSError:
        return ""


def _slug(t):
    return re.sub(r'[^a-z0-9]+', '-', str(t).lower()).strip('-') or "x"


def game_tasks(work, spec_path, gate, status_for, shots_dir):
    """Build the task graph a GAME actually needs.

    The app path keys off nav-graph nodes and endpoints. For a game those are the
    wrong spine: nav-graph nodes are `*View` TYPE NAMES (hundreds of them, with no
    screenshot to diff against), and the endpoint list describes a backend a local
    rebuild stubs. The real specification is `reconstruction/` plus the measured
    `asset-guide/` and `game-assets/`. This function reads those.
    """
    G = os.path.join(work, "game-assets")
    AG = os.path.join(work, "asset-guide")
    REC = os.path.join(os.path.dirname(work), "deliverables", "reconstruction")
    if not os.path.isdir(REC):
        REC = os.path.join(work, "reconstruction")
    tasks, ids = [], []

    def add(tid, ttype, title, inputs, instructions, deps, status="pending"):
        tasks.append({"id": tid, "type": ttype, "title": title,
                      "inputs": [i for i in inputs if i],
                      "instructions": instructions, "gate": gate(ttype),
                      "status": status, "depends_on": deps})
        ids.append(tid)

    # 1. measured engine settings, before any gameplay code
    ps = os.path.join(G, "project-settings")
    if os.path.isdir(ps):
        add("engine-settings", "engine-settings",
            "Apply the measured engine settings",
            [ps, os.path.join(G, "physics.json")],
            "Apply physics, time, quality, layers and the LAYER COLLISION MATRIX from "
            "project-settings/ — these are measured from the original, not defaults. "
            "Do this before writing gameplay code.",
            ["scaffold"])

    # 2. art import, grouped by archetype from the generated index
    idx = os.path.join(AG, "ASSET-INDEX.tsv")
    arche = {}
    if os.path.isfile(idx):
        lines = _read(idx).splitlines()
        if lines:
            head = lines[0].split("\t")
            ai = head.index("archetype") if "archetype" in head else 1
            ni = head.index("nodes") if "nodes" in head else -1
            for ln in lines[1:]:
                c = ln.split("\t")
                if len(c) <= ai:
                    continue
                a = c[ai] or "misc"
                arche.setdefault(a, [0, 0])
                arche[a][0] += 1
                if ni >= 0 and len(c) > ni and c[ni] not in ("-", ""):
                    arche[a][1] += 1
    for a in sorted(arche):
        n, withnodes = arche[a]
        add("art-%s" % _slug(a), "art-import",
            "Import %d '%s' entities as prefabs" % (n, a),
            [idx, os.path.join(G, "entities")],
            "Build a prefab per entity in the '%s' family. **Build from `entity.json` -> "
            "`nodes`**: parent, localPosition/Rotation/Scale, mesh_file, materials IN SLOT "
            "ORDER, active, fracture (debris under a disabled root). %d of these carry a node "
            "tree. The flat mesh list is an index, not a recipe. Check COMPONENT-RECIPES.md "
            "for the component stack this family needs." % (a, withnodes),
            ["engine-settings"] if os.path.isdir(ps) else ["scaffold"])

    # 3. mechanics, from the reconstruction's own chapter headings
    mech_doc = os.path.join(REC, "02-GAMEPLAY-MECHANICS.md")
    mechs = []
    if os.path.isfile(mech_doc):
        for m in re.finditer(r'(?m)^##\s+\d+[.)]?\s+(.+?)\s*$', _read(mech_doc)):
            t = m.group(1).strip()
            if 3 < len(t) < 70:
                mechs.append(t)
    for t in mechs[:40]:
        add("mechanic-%s" % _slug(t)[:40], "mechanic",
            "Implement mechanic: %s" % t,
            [mech_doc], "TDD this mechanic against its section in 02-GAMEPLAY-MECHANICS.md. "
            "Honour the evidence tags: [D]/[S] are facts to reproduce, [I] is an inference to "
            "state, [X] is unknown - take the value from 05-UNKNOWNS.md, do not invent it.",
            ["engine-settings"] if os.path.isdir(ps) else ["scaffold"])

    # 4. level pipeline — nothing ships with the level DB in a live-content game
    if os.path.isdir(os.path.join(G, "levels")) or mechs:
        add("level-schema", "level-pipeline", "Define the level schema + validators",
            [REC, os.path.join(G, "levels")],
            "Define the level JSON schema and its validators, and a content hash. "
            "Recovered accessor/validator names give the shape; the JSON key names are "
            "yours to choose.", ["scaffold"])
        add("level-editor", "level-pipeline", "Level editor + image importer",
            [REC], "An in-editor authoring window: draw the board, place features, validate, "
            "hash, save. Add an image importer that snaps a picture to the palette - it is the "
            "fastest way to author content.", ["level-schema"])
        add("level-loader", "level-pipeline", "Runtime level load + cache + save/resume",
            [REC], "Load levels from StreamingAssets, cache them, and serialise mid-level "
            "state so backgrounding the app never loses a level.", ["level-schema"])

    # 5. real screens: the canvas dump, not `*View` type names
    ui_dir = os.path.join(G, "ui")
    if os.path.isdir(ui_dir):
        canvases = sorted(f for f in os.listdir(ui_dir) if f.endswith(".json"))
        sized = []
        for f in canvases:
            d = load_json(os.path.join(ui_dir, f))
            n = 0
            if isinstance(d, dict):
                def cnt(x):
                    return 1 + sum(cnt(c) for c in (x.get("children") or []))
                n = cnt(d.get("tree", {})) if d.get("tree") else 0
            sized.append((n, f))
        sized.sort(key=lambda t: (-t[0], t[1]))
        for n, f in sized[:25]:
            name = os.path.splitext(f)[0]
            add("ui-%s" % _slug(name)[:40], "scene",
                "Build screen: %s (%d nodes)" % (name, n),
                [os.path.join(ui_dir, f), os.path.join(AG, "UI-ELEMENT-INDEX.tsv"), shots_dir],
                "Rebuild this canvas from its RectTransform tree. Node name, screen zone and "
                "size are measured FACT; sprite candidates in UI-ELEMENT-INDEX.tsv are name "
                "matches - open the PNG before using one. A control is often plate + icon + "
                "hitbox, not one sprite.",
                ["art-ui"] if "art-ui" in ids else ["scaffold"])

    # 6. tuning backlog — the numbers the extraction cannot recover
    unk = os.path.join(REC, "05-UNKNOWNS.md")
    if os.path.isfile(unk):
        secs = re.findall(r'(?m)^###\s+[\d.]+\s+(.+?)\s*$', _read(unk))
        for t in secs[:12]:
            add("tune-%s" % _slug(t)[:40], "tuning", "Tune: %s" % t, [unk],
                "Run the experiment in 05-UNKNOWNS.md for this group and record the value "
                "chosen, or state explicitly that it is deferred. Never invent a number that "
                "the document frames as an experiment.",
                ["level-loader"] if "level-loader" in ids else ["scaffold"])
    return tasks, ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    spec_path = os.path.abspath(args.spec)
    work = os.path.abspath(args.work)
    with open(spec_path) as f:
        spec_text = f.read()

    branch, substack = detect_branch(spec_text)
    package = field(spec_text, "Package") or "unknown"
    mt = re.search(r'(?m)^#\s+Clone Build Spec\s*[—-]\s*(.+)$', spec_text)
    title = mt.group(1).strip() if mt else package

    # --- gaps / completeness ---
    gaps = []
    # A game clone stubs the backend and rebuilds from reconstruction/ + asset-guide/,
    # so the app-shaped artifacts are not what it is missing. Judge it on its own inputs.
    required = REQUIRED if branch != "game" else []
    if branch == "game":
        for req, why in (("game-assets", "no extracted content - run clone-app's Unity extraction"),
                         ("asset-guide", "no asset-usage guide - run clone-app Phase 2f"),):
            if not os.path.isdir(os.path.join(work, req)):
                gaps.append({"artifact": req + "/", "reason": why})
        rec = os.path.join(os.path.dirname(work), "deliverables", "reconstruction")
        if not os.path.isdir(rec) and not os.path.isdir(os.path.join(work, "reconstruction")):
            gaps.append({"artifact": "reconstruction/",
                         "reason": "no reconstruction - run clone-app Phase 5"})
    for req in required:
        p = os.path.join(work, req)
        if not os.path.exists(p):
            gaps.append({"artifact": req, "reason": "missing"})
        else:
            d = load_json(p)
            if d in (None, [], {}):
                gaps.append({"artifact": req, "reason": "empty or invalid JSON"})

    shots_dir = os.path.join(work, "screenshots")
    if not os.path.isdir(shots_dir):
        alt = os.path.join(work, "store", "screenshots")
        if os.path.isdir(alt):
            shots_dir = alt
    shots = sorted(f for f in os.listdir(shots_dir)
                   if f.lower().endswith(".png")) if os.path.isdir(shots_dir) else []
    if not shots and branch != "game":
        gaps.append({"artifact": "screenshots/", "reason": "no PNG screenshots"})

    missing = {g["artifact"] for g in gaps}

    def status_for(deps):
        return "needs-human-input" if any(a in missing for a in deps) else "pending"

    dtokens = os.path.join(work, "design-tokens.json")
    payloads_path = os.path.join(work, "payloads.json")
    nav_path = os.path.join(work, "nav-graph.json")
    logic_path = os.path.join(work, "logic-signals.json")
    logic_digest = os.path.join(work, "logic-digest.md")

    tasks = []

    # 1. scaffold
    tasks.append({
        "id": "scaffold", "type": "scaffold",
        "title": "Scaffold buildable %s project" % branch,
        "inputs": [spec_path],
        "instructions": "Create an empty buildable project per the %s branch guide "
                        "(substack: %s)." % (branch, substack),
        "gate": gate("scaffold"), "status": "pending", "depends_on": [],
    })

    if branch == "game":
        gtasks, gids = game_tasks(work, spec_path, gate, status_for, shots_dir)
        tasks.extend(gtasks)
        tasks.append({
            "id": "integration", "type": "integration",
            "title": "End-to-end integration verify",
            "inputs": [spec_path],
            "instructions": "Build, launch, play the first levels end to end; confirm no "
                            "crash, the core loop resolves, and backgrounding never loses a "
                            "level.",
            "gate": gate("integration"), "status": "pending",
            "depends_on": gids,
        })
        plan = {"package": package, "title": title, "branch": branch,
                "substack": substack, "generated_from": spec_path,
                "gaps": gaps, "tasks": tasks}
        with open(args.out, "w") as f:
            json.dump(plan, f, indent=2)
            f.write("\n")
        print("wrote %s (%d tasks, %d gaps)" % (args.out, len(tasks), len(gaps)))
        return

    # 2. design-system
    tasks.append({
        "id": "design-system", "type": "design",
        "title": "Implement design system",
        "inputs": [dtokens, spec_path],
        "instructions": "Apply the color/type/spacing/radius tokens from "
                        "design-tokens.json as the app theme.",
        "gate": gate("design"),
        "status": status_for(["design-tokens.json"]),
        "depends_on": ["scaffold"],
    })

    # 3. screens from nav-graph nodes
    nav = load_json(nav_path) or {}
    nodes = nav.get("nodes", []) if isinstance(nav, dict) else []
    screen_type = "scene" if branch == "game" else "ui"
    screen_ids = []
    for node in sorted(nodes, key=lambda n: str(n.get("id", ""))):
        nid = str(node.get("id", ""))
        if not nid:
            continue
        tid = "screen-%s" % nid
        screen_ids.append(tid)
        tasks.append({
            "id": tid, "type": screen_type,
            "title": "Build %s screen: %s" % (branch, node.get("label", nid)),
            "inputs": [spec_path, dtokens, shots_dir],
            "instructions": "Build the '%s' screen to match its target screenshot "
                            "and the spec screen entry." % nid,
            "gate": gate(screen_type),
            "status": status_for(["nav-graph.json", "screenshots/"]),
            "depends_on": ["design-system"],
        })

    # 4. api tasks from payloads
    payloads = load_json(payloads_path) or []
    eps = payloads if isinstance(payloads, list) else payloads.get("endpoints", [])
    def ep_key(e):
        return (str(e.get("host", "")), str(e.get("path", "")), str(e.get("method", "")))
    api_ids = []
    for i, ep in enumerate(sorted(eps, key=ep_key), 1):
        tid = "api-%02d" % i
        api_ids.append(tid)
        tasks.append({
            "id": tid, "type": "api",
            "title": "Implement API client: %s %s" % (ep.get("method", "?"), ep.get("path", "?")),
            "inputs": [payloads_path],
            "instructions": "Implement and contract-test the %s %s call per "
                            "payloads.json." % (ep.get("method", "?"), ep.get("path", "?")),
            "gate": gate("api"),
            "status": status_for(["payloads.json"]),
            "depends_on": ["scaffold"],
        })

    # 5. logic tasks (optional artifact)
    logic = load_json(logic_path)
    if isinstance(logic, dict):
        signals = logic.get("signals", logic.get("items", []))
        names = []
        if isinstance(signals, list):
            for s in signals:
                names.append(str(s.get("name", s) if isinstance(s, dict) else s))
        for name in sorted(set(names)):
            safe = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or "rule"
            tasks.append({
                "id": "logic-%s" % safe, "type": "logic",
                "title": "Implement logic: %s" % name,
                "inputs": [logic_path, logic_digest],
                "instructions": "TDD the '%s' rule per logic-signals.json / "
                                "logic-digest.md." % name,
                "gate": gate("logic"), "status": "pending",
                "depends_on": ["scaffold"],
            })

    # 6. integration (always last)
    tasks.append({
        "id": "integration", "type": "integration",
        "title": "End-to-end integration verify",
        "inputs": [spec_path, nav_path],
        "instructions": "Build, launch, and walk every screen/flow; confirm no crash "
                        "and navigation matches nav-graph.json.",
        "gate": gate("integration"), "status": "pending",
        "depends_on": screen_ids + api_ids,
    })

    plan = {
        "package": package, "title": title, "branch": branch, "substack": substack,
        "generated_from": spec_path, "gaps": gaps, "tasks": tasks,
    }
    with open(args.out, "w") as f:
        json.dump(plan, f, indent=2)
        f.write("\n")
    print("wrote %s (%d tasks, %d gaps)" % (args.out, len(tasks), len(gaps)))


main()
