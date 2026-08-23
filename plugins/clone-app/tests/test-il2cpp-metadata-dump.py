#!/usr/bin/env python3
"""Offline tests for il2cpp-metadata-dump.py.

A real global-metadata.dat is 15 MB, so the fixture is a synthetic one built
here: a valid header, a string blob, and type/field/method/property/image tables
laid out the way Unity writes them. That exercises the table auto-discovery,
which is the part that breaks when a metadata version shifts.
"""
import importlib.util
import json
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "clone-app", "scripts", "il2cpp-metadata-dump.py")

spec = importlib.util.spec_from_file_location("il2cpp_metadata_dump", SCRIPT)
md = importlib.util.module_from_spec(spec)
spec.loader.exec_module(md)

fails = []


def check(name, cond):
    print(f"{'PASS' if cond else 'FAIL'}: {name}")
    if not cond:
        fails.append(name)


def build_fixture(path):
    """Synthesize a metadata file with 2 types, 3 fields, 4 methods, 1 property."""
    strings, offsets = bytearray(), {}

    def s(text):
        if text not in offsets:
            offsets[text] = len(strings)
            strings.extend(text.encode() + b"\0")
        return offsets[text]

    names = ["<Module>", "BallController", "Core", "InitialSpeed", "AimContactOffset",
             "m_ball", "Awake", "LaunchBall", ".ctor", "Update", "CanShoot",
             "HasReadyBall", "LoadedBall", "get_CanShoot", "Game.dll", "Core.dll"]
    for n in names:
        s(n)

    # 2 type definitions, 88 bytes each
    types = bytearray()

    def type_def(name_i, ns_i, field_start, method_start, prop_start,
                 method_count, prop_count, field_count):
        v = [name_i, ns_i, 0, -1, 0, 0, -1, 0,
             field_start, method_start, 0, prop_start, 0, 0, 0, 0]
        b = struct.pack("<16i", *v)
        b += struct.pack("<8H", method_count, prop_count, field_count, 0, 0, 0, 0, 0)
        b += struct.pack("<2I", 0, 0)
        return b

    types += type_def(s("<Module>"), s(""), 0, 0, 0, 0, 0, 0)
    types += type_def(s("BallController"), s("Core"), 0, 0, 0, 4, 3, 3)

    fields = b"".join(struct.pack("<iiI", s(n), 0, 0)
                      for n in ("InitialSpeed", "AimContactOffset", "m_ball"))
    fields += struct.pack("<iiI", s("m_ball"), 0, 0) * 200      # padding rows

    methods = b"".join(struct.pack("<iiiiiiiHHHH", s(n), 1, 0, 0, 0, -1, 0, 0, 0, 0, 0)
                       for n in ("Awake", "LaunchBall", ".ctor", "Update"))
    methods += struct.pack("<iiiiiiiHHHH", s("Update"), 1, 0, 0, 0, -1, 0, 0, 0, 0, 0) * 200

    props = b"".join(struct.pack("<5i", s(n), 0, 0, 0, 0)
                     for n in ("CanShoot", "HasReadyBall", "LoadedBall"))
    props += struct.pack("<5i", s("CanShoot"), 0, 0, 0, 0) * 200

    images = struct.pack("<10i", s("Core.dll"), 0, 0, 2, 0, 0, 0, 0, 0, 0)

    sections = [bytes(strings), bytes(types), fields, methods, props, images]
    header_slots = 40
    header_size = 8 + header_slots * 8
    body, meta = bytearray(), []
    off = header_size
    for sec in sections:
        pad = (-len(body)) % 4
        body.extend(b"\0" * pad)
        off = header_size + len(body)
        meta.append((off, len(sec)))
        body.extend(sec)

    header = bytearray(struct.pack("<Ii", 0xFAB11BAF, 31))
    for i in range(header_slots):
        header.extend(struct.pack("<ii", *(meta[i] if i < len(meta) else (header_size, 0))))
    with open(path, "wb") as f:
        f.write(bytes(header) + bytes(body))


with tempfile.TemporaryDirectory() as td:
    fixture = os.path.join(td, "global-metadata.dat")
    build_fixture(fixture)

    m = md.Metadata(fixture)
    check("version parsed", m.version == 31)
    check("type table located", m.tables.get("types") is not None)
    check("type count", m.type_count == 2)
    check("field table located", m.tables.get("fields") is not None)
    check("method table located", m.tables.get("methods") is not None)
    check("images located", m.tables.get("images") is not None)

    surface, stats = md.build_surface(m)
    types = surface.get("Core.dll", {})
    check("type resolved with namespace", "Core.BallController" in types)
    entry = types.get("Core.BallController", {})
    check("fields resolved",
          entry.get("fields") == ["InitialSpeed", "AimContactOffset", "m_ball"])
    check("methods resolved", set(entry.get("methods", [])) ==
          {"Awake", "LaunchBall", ".ctor", "Update"})
    check("accessors split out", entry.get("accessors") == [])
    check("properties resolved",
          entry.get("properties") == ["CanShoot", "HasReadyBall", "LoadedBall"])
    check("totals counted", stats["types"] == 2 and stats["fields"] == 3)

    out = os.path.join(td, "api.json")
    mdown = os.path.join(td, "api.md")
    rc = subprocess.call([sys.executable, SCRIPT, fixture, "--out", out,
                          "--markdown", mdown, "--quiet"])
    check("cli exits 0", rc == 0)
    payload = json.load(open(out))
    check("json has assemblies", "assemblies" in payload and payload["metadata_version"] == 31)
    text = open(mdown).read()
    check("markdown names the type", "BallController" in text)
    check("markdown states the limit", "not recoverable" in text.lower())

    bad = os.path.join(td, "bad.dat")
    open(bad, "wb").write(b"nope" * 100)
    try:
        md.Metadata(bad)
        check("rejects a non-metadata file", False)
    except ValueError:
        check("rejects a non-metadata file", True)

sys.exit(1 if fails else 0)
