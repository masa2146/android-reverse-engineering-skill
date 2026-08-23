#!/usr/bin/env python3
"""Dump the C# API surface out of an IL2CPP `global-metadata.dat`.

No .NET, no Il2CppInspector, no libil2cpp.so — stdlib only. Method *bodies* are
AOT-compiled and unrecoverable, but the metadata still carries every type, field,
method, property and const value name, which is the skeleton of the game's
systems: what each manager owns, what it can do, and which constants it ships.

Table locations are **discovered by validation** rather than hardcoded per
metadata version: each candidate section is scored by how many of its entries
resolve to sane identifiers. That keeps this working across Unity versions
without a per-version layout table.

Usage:
  il2cpp-metadata-dump.py <global-metadata.dat> --out api-surface.json
                          [--markdown api-surface.md] [--assemblies Core,Assembly-CSharp]
"""
import argparse
import collections
import json
import os
import re
import struct
import sys

SANITY = 0xFAB11BAF
# `.ctor`/`.cctor` are the most common method names in any assembly, so the
# leading dot has to be allowed or the method table never validates.
IDENT_RE = re.compile(r"^[.A-Za-z_<][\w<>`.|,\[\]\-+$@ ]*$")

# struct sizes, stable across the v24..v31 range this tool targets
SZ_TYPE = 88      # Il2CppTypeDefinition
SZ_FIELD = 12     # Il2CppFieldDefinition   {nameIndex, typeIndex, token}
SZ_METHOD = 36    # Il2CppMethodDefinition
SZ_IMAGE = 40     # Il2CppImageDefinition
SZ_PROP = 20      # Il2CppPropertyDefinition {name, get, set, attrs, token}
SZ_FIELD_DEFAULT = 12  # Il2CppFieldDefaultValue {fieldIndex, typeIndex, dataIndex}

TYPE_STRUCT = struct.Struct("<16i8H2I")


class Metadata:
    def __init__(self, path):
        with open(path, "rb") as f:
            self.d = f.read()
        sanity, self.version = struct.unpack_from("<Ii", self.d, 0)
        if sanity != SANITY:
            raise ValueError(f"not a global-metadata.dat (sanity 0x{sanity:X})")
        self.sections = self._read_header()
        self.str_off = self.str_size = None
        self.tables = {}
        self._locate()

    # -- header ----------------------------------------------------------
    def _read_header(self):
        out = []
        for i in range(2, 80, 2):
            try:
                off, size = struct.unpack_from("<ii", self.d, i * 4)
            except struct.error:
                break
            if off < 0 or size < 0 or off > len(self.d) or off + size > len(self.d):
                break
            out.append((off, size))
        return out

    # -- string blob ------------------------------------------------------
    def s(self, idx):
        if idx is None or idx < 0 or idx >= self.str_size:
            return None
        end = self.d.find(b"\0", self.str_off + idx)
        if end < 0:
            return None
        try:
            return self.d[self.str_off + idx:end].decode("utf-8", "replace")
        except Exception:
            return None

    @staticmethod
    def _sane(name):
        return bool(name) and len(name) < 300 and bool(IDENT_RE.match(name))

    # -- table discovery --------------------------------------------------
    def _score_types(self, str_off, str_size, off, size, sample=400):
        n = size // SZ_TYPE
        if n < 2:
            return 0, n
        prev = (self.str_off, self.str_size)
        self.str_off, self.str_size = str_off, str_size
        ok = 0
        step = max(1, n // sample)
        checked = 0
        for k in range(0, n, step):
            ni, _ = struct.unpack_from("<ii", self.d, off + k * SZ_TYPE)
            checked += 1
            if self._sane(self.s(ni)):
                ok += 1
            if checked >= sample:
                break
        self.str_off, self.str_size = prev
        return (ok / checked if checked else 0), n

    def _locate(self):
        # identifier blob: a text-ish section; pick whichever validates the type table
        # No absolute size floor: a small game has a small identifier blob, and
        # the scoring below is what actually discriminates.
        text_sections = []
        for off, size in self.sections:
            if size < 64:
                continue
            chunk = self.d[off:off + 4096]
            printable = sum(1 for b in chunk if 32 <= b < 127 or b == 0)
            if printable / max(1, len(chunk)) > 0.9:
                text_sections.append((off, size))

        best = (0, None, None, 0)
        for str_off, str_size in text_sections:
            for off, size in self.sections:
                if not size or size % SZ_TYPE:
                    continue
                score, n = self._score_types(str_off, str_size, off, size)
                if score > best[0]:
                    best = (score, (str_off, str_size), (off, size), n)
        if best[0] < 0.8:
            raise ValueError("could not locate the type-definition table")
        (self.str_off, self.str_size) = best[1]
        self.tables["types"] = best[2]
        self.type_count = best[3]

        # Anchor on many types, and require the table to be large enough for the
        # highest index any type references — that bound alone eliminates most
        # same-stride sections, and the name check settles the rest.
        anchors = collections.defaultdict(list)
        needed = collections.Counter()
        stride = max(1, self.type_count // 40)   # spread anchors across the table
        for i in range(self.type_count):
            t = self.type_raw(i)
            for key, count_key, start_key in (("fields", "fieldCount", "fieldStart"),
                                              ("methods", "methodCount", "methodStart"),
                                              ("properties", "propCount", "propStart")):
                c, st = t[count_key], t[start_key]
                if c <= 0 or st < 0:
                    continue
                needed[key] = max(needed[key], st + c)
                if len(anchors[key]) < 40 and (i % stride == 0 or len(anchors[key]) == 0):
                    anchors[key].append((st, c))
        for key, sz in (("fields", SZ_FIELD), ("methods", SZ_METHOD),
                        ("properties", SZ_PROP)):
            self.tables[key] = self._find_named_table(anchors[key], sz, needed[key])
        self.tables["images"] = self._find_images()
        self.tables["field_defaults"] = self._find_field_defaults()

    def _find_named_table(self, anchors, sz, needed):
        if not anchors or not needed:
            return None
        best = (0, None)
        for off, size in self.sections:
            if not size or size % sz:
                continue
            n = size // sz
            if n < needed:           # cannot hold every index the types reference
                continue
            names = []
            for start, count in anchors:
                for k in range(start, start + min(count, 6)):
                    p = off + k * sz
                    if p + 4 > len(self.d):
                        break
                    ni, = struct.unpack_from("<i", self.d, p)
                    names.append(self.s(ni))
            if not names:
                continue
            ratio = sum(1 for x in names if self._sane(x)) / len(names)
            # prefer the tightest table that still validates
            if ratio > best[0] + 1e-9 or (abs(ratio - best[0]) < 1e-9 and best[1]
                                          and size < best[1][1]):
                best = (ratio, (off, size))
        return best[1] if best[0] >= 0.9 else None

    def _find_images(self):
        best = (0, None)
        for off, size in self.sections:
            if not size or size % SZ_IMAGE:
                continue
            n = size // SZ_IMAGE
            if not (1 <= n <= 5000):
                continue
            good = 0
            for k in range(min(n, 50)):
                ni, = struct.unpack_from("<i", self.d, off + k * SZ_IMAGE)
                nm = self.s(ni)
                if nm and nm.endswith(".dll"):
                    good += 1
            ratio = good / min(n, 50)
            if ratio > best[0]:
                best = (ratio, (off, size))
        return best[1] if best[0] >= 0.8 else None

    def _find_field_defaults(self):
        """Const / default field values — the literal constants the game ships."""
        fields = self.tables.get("fields")
        if not fields:
            return None
        field_count = fields[1] // SZ_FIELD
        best = (0, None)
        for off, size in self.sections:
            if not size or size % SZ_FIELD_DEFAULT:
                continue
            n = size // SZ_FIELD_DEFAULT
            if not (1 <= n <= field_count):
                continue
            ok = 0
            for k in range(min(n, 200)):
                fi, ti, di = struct.unpack_from("<iii", self.d, off + k * SZ_FIELD_DEFAULT)
                if 0 <= fi < field_count and di >= -1:
                    ok += 1
            ratio = ok / min(n, 200)
            if ratio > best[0]:
                best = (ratio, (off, size))
        return best[1] if best[0] >= 0.95 else None

    # -- accessors --------------------------------------------------------
    def type_raw(self, i):
        off = self.tables["types"][0]
        v = TYPE_STRUCT.unpack_from(self.d, off + i * SZ_TYPE)
        return {"nameIndex": v[0], "nsIndex": v[1], "parentIndex": v[4],
                "flags": v[7], "fieldStart": v[8], "methodStart": v[9],
                "eventStart": v[10], "propStart": v[11],
                "methodCount": v[16], "propCount": v[17], "fieldCount": v[18],
                "token": v[25]}

    def name_at(self, table, index):
        t = self.tables.get(table)
        if not t:
            return None
        sz = {"fields": SZ_FIELD, "methods": SZ_METHOD, "properties": SZ_PROP}[table]
        off, size = t
        if index < 0 or (index + 1) * sz > size:
            return None
        ni, = struct.unpack_from("<i", self.d, off + index * sz)
        return self.s(ni)

    def images(self):
        t = self.tables.get("images")
        if not t:
            return []
        off, size = t
        out = []
        for k in range(size // SZ_IMAGE):
            ni, ai, ts, tc = struct.unpack_from("<iiii", self.d, off + k * SZ_IMAGE)
            nm = self.s(ni)
            if nm:
                out.append({"name": nm, "typeStart": ts, "typeCount": tc})
        return out


def build_surface(md, only_assemblies=None):
    images = md.images()
    type_asm = {}
    for img in images:
        for i in range(img["typeStart"], img["typeStart"] + img["typeCount"]):
            type_asm[i] = img["name"]

    out = collections.defaultdict(dict)
    stats = collections.Counter()
    for i in range(md.type_count):
        t = md.type_raw(i)
        name = md.s(t["nameIndex"])
        if not name:
            continue
        asm = type_asm.get(i, "unknown")
        if only_assemblies and asm.replace(".dll", "") not in only_assemblies:
            continue
        ns = md.s(t["nsIndex"]) or ""
        full = f"{ns}.{name}" if ns else name
        fields = [md.name_at("fields", k)
                  for k in range(t["fieldStart"], t["fieldStart"] + t["fieldCount"])]
        methods = [md.name_at("methods", k)
                   for k in range(t["methodStart"], t["methodStart"] + t["methodCount"])]
        props = [md.name_at("properties", k)
                 for k in range(t["propStart"], t["propStart"] + t["propCount"])]
        parent = None
        entry = {
            "namespace": ns,
            "fields": [f for f in fields if f],
            "properties": [p for p in props if p],
            "methods": [m for m in methods if m and not m.startswith(("get_", "set_"))],
            "accessors": [m for m in methods if m and m.startswith(("get_", "set_"))],
            "parent": parent,
        }
        out[asm][full] = entry
        stats["types"] += 1
        stats["fields"] += len(entry["fields"])
        stats["methods"] += len(entry["methods"])
        stats["properties"] += len(entry["properties"])
    return dict(out), dict(stats)


def render_markdown(surface, title):
    lines = [f"# {title}", "",
             "Recovered from `global-metadata.dat` — type, field, method and property",
             "**names** only. Method *bodies* are AOT-compiled into `libil2cpp.so` and",
             "are not recoverable, so no formula or constant expression appears here.",
             "What this gives you is the exact shape of every system: what each class",
             "owns and what it can do.", ""]
    for asm in sorted(surface, key=lambda a: -len(surface[a])):
        types = surface[asm]
        lines.append(f"## `{asm}` — {len(types)} types")
        lines.append("")
        by_ns = collections.defaultdict(list)
        for full, e in types.items():
            by_ns[e["namespace"] or "(global)"].append((full, e))
        for ns in sorted(by_ns):
            lines.append(f"### {ns}")
            lines.append("")
            for full, e in sorted(by_ns[ns]):
                short = full.rsplit(".", 1)[-1]
                lines.append(f"#### `{short}`")
                if e["fields"]:
                    lines.append("- **fields:** " + ", ".join(f"`{f}`" for f in e["fields"]))
                if e["properties"]:
                    lines.append("- **properties:** " + ", ".join(f"`{p}`" for p in e["properties"]))
                if e["methods"]:
                    lines.append("- **methods:** " + ", ".join(f"`{m}`" for m in e["methods"]))
                lines.append("")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("metadata")
    ap.add_argument("--out", required=True, help="JSON output path")
    ap.add_argument("--markdown", help="also render a Markdown API surface")
    ap.add_argument("--assemblies",
                    help="comma-separated assembly filter, e.g. Core,Assembly-CSharp")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    md = Metadata(args.metadata)
    only = set(a.strip() for a in args.assemblies.split(",")) if args.assemblies else None
    surface, stats = build_surface(md, only)

    payload = {"metadata_version": md.version,
               "tables": {k: v for k, v in md.tables.items()},
               "totals": stats,
               "assemblies": surface}
    with open(args.out, "w") as f:
        json.dump(payload, f, indent=1, ensure_ascii=False)
    if args.markdown:
        with open(args.markdown, "w") as f:
            f.write(render_markdown(surface, "IL2CPP API surface"))
    if not args.quiet:
        print(f"metadata v{md.version} · {md.type_count} types in package")
        print("tables: " + ", ".join(f"{k}={'found' if v else 'MISSING'}"
                                     for k, v in md.tables.items()))
        print(f"dumped: {stats.get('types', 0)} types, {stats.get('fields', 0)} fields, "
              f"{stats.get('methods', 0)} methods, {stats.get('properties', 0)} properties")
        print(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
