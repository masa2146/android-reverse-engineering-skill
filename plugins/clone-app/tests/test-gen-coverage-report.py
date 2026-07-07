import json, subprocess, sys, tempfile, os

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "clone-app", "scripts", "gen-coverage-report.py")

MANIFEST = {
    "engine": "unity-il2cpp",
    "assets": {"expected": 512, "extracted": 340, "by_type": {"texture": 300, "audio": 40}},
    "mechanics": [
        {"name": "DamageFormula", "confidence": "signature-only"},
        {"name": "DropTable", "confidence": "inferred"},
    ],
    "notes": ["il2cpp method bodies not recovered"],
}

def run(manifest):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(manifest, f)
        path = f.name
    out = subprocess.run([sys.executable, SCRIPT, path], capture_output=True, text=True)
    os.unlink(path)
    assert out.returncode == 0, out.stderr
    return out.stdout

def test_partial_ratio_shown():
    md = run(MANIFEST)
    assert "340/512" in md, md
    assert "partial" in md.lower(), md

def test_confidence_grouping():
    md = run(MANIFEST)
    assert "signature-only" in md and "inferred" in md, md
    assert "DamageFormula" in md and "DropTable" in md, md

def test_notes_and_missing_count():
    md = run(MANIFEST)
    assert "il2cpp method bodies not recovered" in md, md
    assert "172" in md, md  # 512 - 340 unaccounted

def test_full_coverage_reads_covered():
    m = dict(MANIFEST); m["assets"] = {"expected": 10, "extracted": 10, "by_type": {"texture": 10}}
    md = run(m)
    assert "covered" in md.lower(), md

if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn(); print(f"PASS: {name}")
    print("ALL PASSED")
