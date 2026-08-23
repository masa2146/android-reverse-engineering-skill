#!/usr/bin/env python3
"""Offline tests for render-mesh-preview.py.

The OBJ parser is stdlib-only and always tested. The rasteriser needs
numpy+Pillow (extraction venv); when they are absent the render assertions skip
rather than fail, so this suite still runs on a bare stdlib python.
"""
import importlib.util
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "clone-app", "scripts", "render-mesh-preview.py")
CUBE = os.path.join(HERE, "fixtures", "unity-sample", "cube.obj")

spec = importlib.util.spec_from_file_location("render_mesh_preview", SCRIPT)
rmp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rmp)

fails = []


def check(name, cond):
    print(f"{'PASS' if cond else 'FAIL'}: {name}")
    if not cond:
        fails.append(name)


verts, faces = rmp.load_obj(CUBE)
check("cube vertices parsed", len(verts) == 8)
check("cube triangles parsed", len(faces) == 12)
check("indices are zero-based", all(0 <= i < 8 for f in faces for i in f))

with tempfile.TemporaryDirectory() as td:
    rel = os.path.join(td, "rel.obj")
    with open(rel, "w") as f:
        f.write("v 0 0 0\nv 1 0 0\nv 0 1 0\nf -3 -2 -1\n")
    _, rf = rmp.load_obj(rel)
    check("negative indices resolved", rf == [[0, 1, 2]])

    quad = os.path.join(td, "quad.obj")
    with open(quad, "w") as f:
        f.write("v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nf 1/1/1 2/2/2 3/3/3 4/4/4\n")
    _, qf = rmp.load_obj(quad)
    check("quad fan-triangulated with v/vt/vn indices", len(qf) == 2)

    empty = os.path.join(td, "empty.obj")
    with open(empty, "w") as f:
        f.write("# nothing here\n")
    ev, ef = rmp.load_obj(empty)
    check("empty obj yields nothing", ev == [] and ef == [])

    try:
        import numpy  # noqa: F401
        from PIL import Image  # noqa: F401
        have_deps = True
    except ImportError:
        have_deps = False

    if not have_deps:
        print("SKIP: numpy/Pillow absent — rasteriser assertions skipped "
              "(run under the extraction venv to cover them)")
    else:
        img = rmp.render(CUBE, size=64)
        check("render returns an image", img is not None)
        check("render honours size", img.size == (64, 64))
        raw = img.convert("RGB").tobytes()
        px = [raw[i:i + 3] for i in range(0, len(raw), 3)]
        bg = px[0]
        check("render is not blank", any(p != bg for p in px))
        lit = sum(1 for p in px if p != bg)
        check("cube covers a plausible area", 200 < lit < 64 * 64)
        check("empty obj renders None", rmp.render(empty, size=32) is None)

        sheet = os.path.join(td, "sheet.png")
        out = rmp.contact_sheet([("cube", img), ("cube2", img)], sheet, cell=64, cols=2)
        check("contact sheet written", out and os.path.getsize(sheet) > 0)

sys.exit(1 if fails else 0)
