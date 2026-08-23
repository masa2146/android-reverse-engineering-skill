#!/usr/bin/env python3
"""Tiny software renderer for extracted OBJ meshes — numpy + Pillow only.

A z-buffered isometric flat-shaded preview. No 3D framework, no headless GL, no
GPU: a 500-mesh extraction is unreviewable as a folder of filenames, and one
contact sheet makes it verifiable at a glance.

Runs under the extraction venv. Imports are lazy so the OBJ parser below stays
testable with the stdlib alone.
"""
import argparse
import math
import os
import sys


def load_obj(path):
    """Parse an OBJ into (vertices, triangles). Faces are fan-triangulated and
    negative (relative) indices are resolved. Returns plain lists."""
    verts, faces = [], []
    with open(path, errors="replace") as f:
        for line in f:
            if line.startswith("v "):
                parts = line.split()
                if len(parts) >= 4:
                    verts.append([float(parts[1]), float(parts[2]), float(parts[3])])
            elif line.startswith("f "):
                idx = []
                for p in line.split()[1:]:
                    token = p.split("/")[0]
                    if not token:
                        continue
                    i = int(token)
                    idx.append(i - 1 if i > 0 else len(verts) + i)
                for k in range(1, len(idx) - 1):
                    faces.append([idx[0], idx[k], idx[k + 1]])
    return verts, faces


def render(path, size=256, background=(28, 28, 34), light=(0.4, 0.7, 0.6),
           yaw_deg=-35.0, pitch_deg=30.0):
    """Render an OBJ to a PIL Image, or None if it has no drawable geometry."""
    import numpy as np
    from PIL import Image

    verts, faces = load_obj(path)
    if not verts or not faces:
        return None
    V = np.asarray(verts, dtype=np.float32)
    F = np.asarray(faces, dtype=np.int32)
    F = F[(F >= 0).all(axis=1) & (F < len(V)).all(axis=1)]
    if len(F) == 0:
        return None

    a, b = math.radians(pitch_deg), math.radians(yaw_deg)
    Rx = np.array([[1, 0, 0],
                   [0, math.cos(a), -math.sin(a)],
                   [0, math.sin(a), math.cos(a)]], dtype=np.float32)
    Ry = np.array([[math.cos(b), 0, math.sin(b)],
                   [0, 1, 0],
                   [-math.sin(b), 0, math.cos(b)]], dtype=np.float32)
    P = V @ Ry.T @ Rx.T
    lo, hi = P.min(0), P.max(0)
    scale = float((hi - lo).max()) or 1.0
    P = (P - (lo + hi) / 2.0) / scale

    xs = (P[:, 0] * 0.85 + 0.5) * size
    ys = (0.5 - P[:, 1] * 0.85) * size
    zs = P[:, 2]

    img = np.empty((size, size, 3), dtype=np.float32)
    img[:] = np.asarray(background, dtype=np.float32) / 255.0
    zbuf = np.full((size, size), 1e9, dtype=np.float32)

    tri = np.stack([np.stack([xs[F[:, i]], ys[F[:, i]], zs[F[:, i]]], -1)
                    for i in range(3)], 1)
    normals = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    norm = np.linalg.norm(normals, axis=1, keepdims=True)
    norm[norm == 0] = 1.0
    normals = (normals / norm) @ Ry.T @ Rx.T
    L = np.asarray(light, dtype=np.float32)
    L = L / np.linalg.norm(L)
    shade = np.clip(np.abs(normals @ L), 0.0, 1.0) * 0.75 + 0.25
    base = np.array([0.72, 0.76, 0.82], dtype=np.float32)

    for f in np.argsort(-tri[:, :, 2].mean(1)):
        t = tri[f]
        x0 = int(max(0, math.floor(t[:, 0].min())))
        x1 = int(min(size - 1, math.ceil(t[:, 0].max())))
        y0 = int(max(0, math.floor(t[:, 1].min())))
        y1 = int(min(size - 1, math.ceil(t[:, 1].max())))
        if x1 < x0 or y1 < y0:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        denom = ((t[1, 1] - t[2, 1]) * (t[0, 0] - t[2, 0]) +
                 (t[2, 0] - t[1, 0]) * (t[0, 1] - t[2, 1]))
        if abs(denom) < 1e-9:
            continue
        w0 = ((t[1, 1] - t[2, 1]) * (gx - t[2, 0]) +
              (t[2, 0] - t[1, 0]) * (gy - t[2, 1])) / denom
        w1 = ((t[2, 1] - t[0, 1]) * (gx - t[2, 0]) +
              (t[0, 0] - t[2, 0]) * (gy - t[2, 1])) / denom
        w2 = 1.0 - w0 - w1
        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not inside.any():
            continue
        depth = w0 * t[0, 2] + w1 * t[1, 2] + w2 * t[2, 2]
        window = zbuf[y0:y1 + 1, x0:x1 + 1]
        write = inside & (depth < window)
        window[write] = depth[write]
        img[y0:y1 + 1, x0:x1 + 1][write] = base * shade[f]

    return Image.fromarray((img * 255).astype("uint8"))


def contact_sheet(cells, out_path, cell=192, cols=10, label_height=18):
    """cells: [(label, PIL.Image)] -> one labelled sheet."""
    from PIL import Image, ImageDraw, ImageFont
    if not cells:
        return None
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * (cell + label_height)), (20, 20, 24))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 12)
    except Exception:
        font = ImageFont.load_default()
    for i, (label, img) in enumerate(cells):
        x, y = (i % cols) * cell, (i // cols) * (cell + label_height)
        if img.size != (cell, cell):
            img = img.resize((cell, cell))
        sheet.paste(img, (x, y))
        draw.text((x + 3, y + cell + 2), str(label)[:28], fill=(220, 220, 230), font=font)
    sheet.save(out_path)
    return out_path


def contact_sheet_from_dir(src_dir, out_path, cell=96, cols=24, limit=600):
    """Flat PNG pool -> one thumbnail sheet (sprites, textures)."""
    from PIL import Image
    files = sorted(f for f in os.listdir(src_dir) if f.lower().endswith(".png"))[:limit]
    if not files:
        return None
    rows = (len(files) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cell, rows * cell), (30, 30, 36, 255))
    for i, f in enumerate(files):
        try:
            im = Image.open(os.path.join(src_dir, f)).convert("RGBA")
        except Exception:
            continue
        im.thumbnail((cell - 4, cell - 4))
        sheet.paste(im, ((i % cols) * cell + 2, (i // cols) * cell + 2), im)
    sheet.save(out_path)
    return out_path


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render an OBJ mesh to a PNG preview.")
    ap.add_argument("obj")
    ap.add_argument("out")
    ap.add_argument("--size", type=int, default=256)
    args = ap.parse_args(argv)
    img = render(args.obj, size=args.size)
    if img is None:
        print(f"ERROR: no drawable geometry in {args.obj}", file=sys.stderr)
        return 1
    img.save(args.out)
    print(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
