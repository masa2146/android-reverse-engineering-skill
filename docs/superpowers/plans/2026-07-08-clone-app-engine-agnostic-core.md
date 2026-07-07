# Engine-Agnostic Extraction Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the engine-agnostic dispatcher core for clone-app Phase 2 — engine detection across Unity/Unreal/Godot, a uniform per-engine output contract, a coverage-report generator, and an isolated extraction venv — so per-engine modules can plug in without bloating the skill's context.

**Architecture:** A new `detect-engine.sh` classifies a package by engine (delegating Unity to the existing `detect-unity.sh`). `SKILL.md` Phase 2 becomes a thin dispatcher that loads only the matching engine's module. Every engine module fills the same contract (`mechanics-digest.md`, `game-assets/` + `manifest.json`, `netcode-recon.md`, `coverage-report.md`); `gen-coverage-report.py` turns a coverage manifest into an honest covered/partial/missing report. Heavy Python tooling lives in an opt-in, git-ignored venv.

**Tech Stack:** bash 4+ (stdlib scripts), Python 3 stdlib (generators + tests), Python `venv`/pip (isolated extraction env only).

## Global Constraints

- **`plugins/android-reverse-engineering/` is untouched** — `git status --porcelain plugins/android-reverse-engineering/` must print nothing.
- **Shipped core scripts + all tests are stdlib-only** — no pip, no third-party imports in `detect-engine.sh`, `gen-coverage-report.py`, or any `test-*`. pip is confined to the extraction venv.
- **bash 4+ at runtime** — scripts use `#!/usr/bin/env bash`, `set -uo pipefail`; invoke with `bash <path>`, never `sh`.
- **Tests are offline + fixture-driven** — no network; build fixture zips with Python's `zipfile` (portable, no `zip` binary).
- **Working dir is `./work/{package}/`** relative to the user's cwd, never inside the plugin.
- **Conventional Commits scoped to the plugin** — `feat(clone-app): …`, `test(clone-app): …`, `chore(clone-app): …`.
- **Engine tokens (exact, verbatim everywhere):** `unity-il2cpp` `unity-mono` `unreal` `godot` `native` `none`.
- **Reference-only asset stance** — extracted art is documented "reference only — recreate in the same style," never a 1:1 copy.

---

### Task 1: `detect-engine.sh` — engine classifier

**Files:**
- Create: `plugins/clone-app/skills/clone-app/scripts/detect-engine.sh`
- Test: `plugins/clone-app/tests/test-detect-engine.sh`

**Interfaces:**
- Consumes: `plugins/clone-app/skills/clone-app/scripts/detect-unity.sh` (existing; prints `il2cpp|mono|none`).
- Produces: `detect-engine.sh <apk-or-xapk>` prints exactly one of `unity-il2cpp|unity-mono|unreal|godot|native|none` to stdout, exit 0; usage error exits 2.

- [ ] **Step 1: Write the failing test**

Create `plugins/clone-app/tests/test-detect-engine.sh`:

```bash
#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/../skills/clone-app/scripts/detect-engine.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
fail=0
check() {
  local desc="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then echo "PASS: $desc"
  else echo "FAIL: $desc — expected '$expected' got '$actual'"; fail=1; fi
}
mkzip() { python3 - "$1" "${@:2}" <<'PY'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1], "w") as z:
    for e in sys.argv[2:]:
        z.writestr(e, "x")
PY
}

mkzip "$TMP/il2cpp.apk" "lib/arm64-v8a/libil2cpp.so" "assets/bin/Data/Managed/Metadata/global-metadata.dat" "classes.dex"
mkzip "$TMP/mono.apk"   "assets/bin/Data/Managed/Assembly-CSharp.dll" "classes.dex"
mkzip "$TMP/unreal.apk" "lib/arm64-v8a/libUE4.so" "assets/paks/game.pak" "classes.dex"
mkzip "$TMP/godot.apk"  "lib/arm64-v8a/libgodot_android.so" "assets/game.pck" "classes.dex"
mkzip "$TMP/native.apk" "lib/arm64-v8a/libmygame.so"
mkzip "$TMP/none.apk"   "classes.dex" "AndroidManifest.xml"

# XAPK wrapping an Unreal base.apk
mkzip "$TMP/ubase.apk" "lib/arm64-v8a/libUnreal.so" "assets/paks/game.pak" "classes.dex"
python3 - "$TMP/unreal.xapk" "$TMP/ubase.apk" <<'PY'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1], "w") as z:
    z.write(sys.argv[2], arcname="base.apk")
    z.writestr("manifest.json", "{}")
PY

check "il2cpp" "unity-il2cpp" "$(bash "$SCRIPT" "$TMP/il2cpp.apk")"
check "mono"   "unity-mono"   "$(bash "$SCRIPT" "$TMP/mono.apk")"
check "unreal" "unreal"       "$(bash "$SCRIPT" "$TMP/unreal.apk")"
check "godot"  "godot"        "$(bash "$SCRIPT" "$TMP/godot.apk")"
check "native" "native"       "$(bash "$SCRIPT" "$TMP/native.apk")"
check "none"   "none"         "$(bash "$SCRIPT" "$TMP/none.apk")"
check "xapk unreal" "unreal"  "$(bash "$SCRIPT" "$TMP/unreal.xapk")"

bash "$SCRIPT" >/dev/null 2>&1; rc=$?
check "usage exit 2" "2" "$rc"

exit $fail
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash plugins/clone-app/tests/test-detect-engine.sh`
Expected: FAIL — `detect-engine.sh` does not exist yet (all checks fail / script not found).

- [ ] **Step 3: Write minimal implementation**

Create `plugins/clone-app/skills/clone-app/scripts/detect-engine.sh`:

```bash
#!/usr/bin/env bash
# Classify a game package by engine:
#   unity-il2cpp | unity-mono | unreal | godot | native | none
# Unity classification is delegated to detect-unity.sh (already XAPK/split-aware);
# Unreal/Godot/native are added here. Unity wins precedence (most specific markers).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
APK="${1:-}"
if [[ -z "$APK" || ! -f "$APK" ]]; then
  echo "ERROR: usage: detect-engine.sh <apk-or-xapk>" >&2
  exit 2
fi

case "$(bash "$HERE/detect-unity.sh" "$APK")" in
  il2cpp) echo unity-il2cpp; exit 0 ;;
  mono)   echo unity-mono;   exit 0 ;;
esac

# Build an XAPK-aware listing for the remaining engines.
listing="$(unzip -Z1 "$APK" 2>/dev/null)" || {
  echo "ERROR: cannot read zip: $APK" >&2; exit 2; }
nested_apks="$(grep -E '\.apk$' <<<"$listing" || true)"
if [[ -n "$nested_apks" ]]; then
  INNER_TMP="$(mktemp -d)"
  trap 'rm -rf "$INNER_TMP"' EXIT
  while IFS= read -r inner; do
    [[ -z "$inner" ]] && continue
    unzip -p "$APK" "$inner" > "$INNER_TMP/x.apk" 2>/dev/null || continue
    listing="$listing"$'\n'"$(unzip -Z1 "$INNER_TMP/x.apk" 2>/dev/null || true)"
  done <<<"$nested_apks"
fi

# Unreal: engine .so, or cooked-content markers.
if grep -Eqi 'lib(ue4|unreal)\.so' <<<"$listing"; then echo unreal; exit 0; fi
if grep -Eq '\.uasset$|\.uexp$' <<<"$listing" && grep -Eq '\.pak$' <<<"$listing"; then echo unreal; exit 0; fi
if grep -Eq 'AssetRegistry\.bin$' <<<"$listing"; then echo unreal; exit 0; fi

# Godot: engine .so, PCK archive, or bootstrap.
if grep -Eqi 'libgodot(_android)?\.so' <<<"$listing"; then echo godot; exit 0; fi
if grep -Eq '\.pck$' <<<"$listing"; then echo godot; exit 0; fi
if grep -Eq '(^|/)project\.binary$' <<<"$listing"; then echo godot; exit 0; fi

# Pure-native game: native libs but NO dex bootstrap (a normal app always has dex).
if ! grep -Eq '(^|/)classes[0-9]*\.dex$' <<<"$listing" \
   && grep -Eq '^lib/[^/]+/.*\.so$' <<<"$listing"; then
  echo native; exit 0
fi

echo none
exit 0
```

- [ ] **Step 4: Verify tests pass**

Run: `bash plugins/clone-app/tests/test-detect-engine.sh`
Expected: all PASS, exit 0.
Also run `bash plugins/clone-app/tests/test-detect-unity.sh` — still green (unchanged).

- [ ] **Step 5: Make script executable + commit**

```bash
chmod +x plugins/clone-app/skills/clone-app/scripts/detect-engine.sh
git add plugins/clone-app/skills/clone-app/scripts/detect-engine.sh plugins/clone-app/tests/test-detect-engine.sh
git commit -m "feat(clone-app): add detect-engine.sh engine classifier"
```

---

### Task 2: `gen-coverage-report.py` — honest coverage rollup

**Files:**
- Create: `plugins/clone-app/skills/clone-app/scripts/gen-coverage-report.py`
- Test: `plugins/clone-app/tests/test-gen-coverage-report.py`

**Interfaces:**
- Consumes: a coverage manifest JSON, shape:
  `{"engine": str, "assets": {"expected": int, "extracted": int, "by_type": {str:int}}, "mechanics": [{"name": str, "confidence": "observed|inferred|signature-only|not-recoverable"}], "notes": [str]}`
- Produces: `python3 gen-coverage-report.py <manifest.json> [--out coverage-report.md]` writes the Markdown report (stdout if `--out` omitted). Rollup rule: `covered` if extracted≥expected, `partial` if 0<extracted<expected, `missing` if extracted==0.

- [ ] **Step 1: Write the failing test**

Create `plugins/clone-app/tests/test-gen-coverage-report.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 plugins/clone-app/tests/test-gen-coverage-report.py`
Expected: FAIL — script missing (FileNotFound / non-zero returncode).

- [ ] **Step 3: Write minimal implementation**

Create `plugins/clone-app/skills/clone-app/scripts/gen-coverage-report.py`:

```python
#!/usr/bin/env python3
"""Turn a coverage manifest into an honest covered/partial/missing report.

Manifest shape:
  {"engine": str,
   "assets": {"expected": int, "extracted": int, "by_type": {type: int}},
   "mechanics": [{"name": str, "confidence": str}],
   "notes": [str]}
Stdlib only.
"""
import argparse, json, sys


def rollup(expected, extracted):
    if extracted >= expected and expected > 0:
        return "COVERED"
    if extracted == 0:
        return "MISSING"
    return "PARTIAL"


def render(m):
    a = m.get("assets", {}) or {}
    exp, ext = int(a.get("expected", 0)), int(a.get("extracted", 0))
    status = rollup(exp, ext)
    unaccounted = max(exp - ext, 0)
    lines = []
    lines.append(f"# Coverage Report — {m.get('engine', 'unknown')}")
    lines.append("")
    lines.append("> Extracted assets are **reference only** — recreate in the same style, not 1:1.")
    lines.append("")
    lines.append("## Assets")
    lines.append(f"- Status: **{status.lower()}** ({ext}/{exp} entries extracted)")
    if unaccounted:
        lines.append(f"- Not extracted: **{unaccounted}** (unsupported format / encrypted / see notes)")
    by_type = a.get("by_type", {}) or {}
    if by_type:
        lines.append("")
        lines.append("| Type | Extracted |")
        lines.append("|---|---|")
        for t in sorted(by_type):
            lines.append(f"| {t} | {by_type[t]} |")
    lines.append("")
    lines.append("## Mechanics (by confidence)")
    buckets = {}
    for item in m.get("mechanics", []) or []:
        buckets.setdefault(item.get("confidence", "unknown"), []).append(item.get("name", "?"))
    if not buckets:
        lines.append("- none recovered")
    for conf in ("observed", "inferred", "signature-only", "not-recoverable", "unknown"):
        if conf in buckets:
            lines.append(f"- **{conf}**: " + ", ".join(sorted(buckets[conf])))
    notes = m.get("notes", []) or []
    if notes:
        lines.append("")
        lines.append("## Notes / why incomplete")
        for n in notes:
            lines.append(f"- {n}")
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    ap.add_argument("--out")
    args = ap.parse_args()
    with open(args.manifest) as f:
        m = json.load(f)
    report = render(m)
    if args.out:
        with open(args.out, "w") as f:
            f.write(report)
    else:
        sys.stdout.write(report)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Verify tests pass**

Run: `python3 plugins/clone-app/tests/test-gen-coverage-report.py`
Expected: all PASS, "ALL PASSED".

- [ ] **Step 5: Commit**

```bash
git add plugins/clone-app/skills/clone-app/scripts/gen-coverage-report.py plugins/clone-app/tests/test-gen-coverage-report.py
git commit -m "feat(clone-app): add gen-coverage-report.py coverage rollup"
```

---

### Task 3: Extraction venv bootstrap

**Files:**
- Create: `plugins/clone-app/skills/clone-app/scripts/setup-extraction-venv.sh`
- Create: `plugins/clone-app/skills/clone-app/scripts/requirements-extraction.txt`
- Modify: `.gitignore` (repo root — add the venv path)
- Test: `plugins/clone-app/tests/test-extraction-venv.sh`

**Interfaces:**
- Produces: `setup-extraction-venv.sh` creates `${EXTRACTION_VENV:-<scripts>/../.venv-extraction}`, installs `requirements-extraction.txt`, prints the venv path. Idempotent (skips venv creation if present). Extractors invoke `"$VENV/bin/python"`.

- [ ] **Step 1: Write the failing test** (offline — structural, no pip/network)

Create `plugins/clone-app/tests/test-extraction-venv.sh`:

```bash
#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
S="$HERE/../skills/clone-app/scripts/setup-extraction-venv.sh"
REQ="$HERE/../skills/clone-app/scripts/requirements-extraction.txt"
ROOT="$(cd "$HERE/../../.." && pwd)"
fail=0
chk() { if eval "$2"; then echo "PASS: $1"; else echo "FAIL: $1"; fail=1; fi; }

chk "setup script exists"        "[[ -f '$S' ]]"
chk "setup script executable"    "[[ -x '$S' ]]"
chk "uses python -m venv"        "grep -q 'python3 -m venv' '$S'"
chk "targets .venv-extraction"   "grep -q '.venv-extraction' '$S'"
chk "installs requirements file" "grep -q 'requirements-extraction.txt' '$S'"
chk "requirements lists UnityPy" "grep -qi 'unitypy' '$REQ'"
chk "gitignore ignores venv"     "grep -q '.venv-extraction' '$ROOT/.gitignore'"

exit $fail
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash plugins/clone-app/tests/test-extraction-venv.sh`
Expected: FAIL — files/gitignore entry missing.

- [ ] **Step 3: Write the implementation**

Create `plugins/clone-app/skills/clone-app/scripts/setup-extraction-venv.sh`:

```bash
#!/usr/bin/env bash
# Create an isolated, opt-in venv for heavy asset-extraction tooling (UnityPy, ...).
# The repo's shipped core scripts + tests stay stdlib-only; this venv is separate
# and git-ignored. Prints the venv path on success.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
VENV="${EXTRACTION_VENV:-$HERE/../.venv-extraction}"
REQ="$HERE/requirements-extraction.txt"
if [[ ! -d "$VENV" ]]; then
  python3 -m venv "$VENV" || { echo "ERROR: venv creation failed" >&2; exit 1; }
fi
"$VENV/bin/pip" install --quiet --upgrade pip || true
"$VENV/bin/pip" install --quiet -r "$REQ" || {
  echo "ERROR: pip install failed (offline? see $REQ)" >&2; exit 1; }
echo "$VENV"
```

Create `plugins/clone-app/skills/clone-app/scripts/requirements-extraction.txt`:

```
UnityPy>=1.20
```

Add to repo-root `.gitignore` (append a line):

```
.venv-extraction/
```

- [ ] **Step 4: Verify tests pass**

Run: `bash plugins/clone-app/tests/test-extraction-venv.sh`
Expected: all PASS.

- [ ] **Step 5: Make executable + commit**

```bash
chmod +x plugins/clone-app/skills/clone-app/scripts/setup-extraction-venv.sh
git add plugins/clone-app/skills/clone-app/scripts/setup-extraction-venv.sh \
        plugins/clone-app/skills/clone-app/scripts/requirements-extraction.txt \
        .gitignore plugins/clone-app/tests/test-extraction-venv.sh
git commit -m "feat(clone-app): add opt-in extraction venv bootstrap"
```

---

### Task 4: Engine module contract reference

**Files:**
- Create: `plugins/clone-app/skills/clone-app/references/engines/module-contract.md`
- Test: `plugins/clone-app/tests/test-engine-contract.sh`

**Interfaces:**
- Produces: the judgment rubric the dispatcher loads for any engine module. Every future per-engine module (Unity/Godot/Unreal) fills exactly the outputs this file defines.

- [ ] **Step 1: Write the failing test**

Create `plugins/clone-app/tests/test-engine-contract.sh`:

```bash
#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DOC="$HERE/../skills/clone-app/references/engines/module-contract.md"
fail=0
has() { if grep -qF "$1" "$DOC"; then echo "PASS: has '$1'"; else echo "FAIL: missing '$1'"; fail=1; fi; }

has "mechanics-digest.md"
has "game-assets/"
has "manifest.json"
has "netcode-recon.md"
has "coverage-report.md"
has "observed"
has "inferred"
has "signature-only"
has "not-recoverable"
has "reference only"

exit $fail
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash plugins/clone-app/tests/test-engine-contract.sh`
Expected: FAIL — file does not exist.

- [ ] **Step 3: Write the contract doc**

Create `plugins/clone-app/skills/clone-app/references/engines/module-contract.md`:

```markdown
# Engine Module Contract

Every per-engine extraction module (unity-il2cpp, unity-mono, unreal, godot,
native) is loaded on demand by `detect-engine.sh` + the Phase 2 dispatcher and
MUST write these four artifacts to `$WORK/`, so the Phase 8 Clone Build Spec
assembler never branches on engine.

## Outputs

1. **`mechanics-digest.md`** — recovered logic / rules / formulas + data-layer
   values (balance tables, curves, drop rates). Every entry carries a confidence
   stamp:
   - `observed` — from near-source (mono/GDScript/Blueprint).
   - `inferred` — from extracted data (ScriptableObjects, DataTables).
   - `signature-only` — il2cpp type model; method body not recovered.
   - `not-recoverable` — native C++ / stripped; flagged, not guessed.
2. **`game-assets/` + `manifest.json`** — extracted textures/sprites/audio/
   meshes/scenes/prefabs/fonts. `manifest.json` records per-type counts and the
   coverage shape consumed by `gen-coverage-report.py`:
   `{"engine", "assets": {"expected", "extracted", "by_type"}, "mechanics", "notes"}`.
   `expected` = archive entry count found in the package; `extracted` = files
   actually written. Never claim more than was written.
3. **`netcode-recon.md`** — observed netcode/backend surface (Photon/PlayFab/
   Mirror/HTTP), same confidence stamps. Complements `backend-recon.md`.
4. **`coverage-report.md`** — produced by
   `gen-coverage-report.py manifest.json --out coverage-report.md`; the honest
   covered/partial/missing rollup. Downstream reads this to avoid mistaking
   partial extraction for complete.

## Decision gates (dispatcher-owned, not module-owned)

- **Dependency gate** — if a module's tool/venv is missing, PAUSE and surface the
  install cost + a `limited:` proceed option. Never degrade silently.
- **Layer-2 escalation** — expensive native disassembly (e.g. il2cpp via Ghidra)
  is offered only when Layer-1 leaves a gap, and only on user consent.

## Legal stance

Extracted assets are copyrighted and recorded **reference only** — recreate in
the same style. This pipeline targets faithful rebuild, not a 1:1 copy.
```

- [ ] **Step 4: Verify tests pass**

Run: `bash plugins/clone-app/tests/test-engine-contract.sh`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/clone-app/skills/clone-app/references/engines/module-contract.md \
        plugins/clone-app/tests/test-engine-contract.sh
git commit -m "feat(clone-app): add engine module contract reference"
```

---

### Task 5: Wire the dispatcher into SKILL.md Phase 2

**Files:**
- Modify: `plugins/clone-app/skills/clone-app/SKILL.md` (Phase 2a — insert an "Engine dispatch" subsection before the existing Unity gate, at the `### Phase 2a — Unity tool dependency gate` heading, line ~69)
- Modify: `plugins/clone-app/tests/test-skill-phases.sh` (add asserts for the new strings)

**Interfaces:**
- Consumes: `detect-engine.sh` (Task 1), `module-contract.md` (Task 4), `gen-coverage-report.py` (Task 2).
- Produces: Phase 2 now resolves an engine token and loads only the matching module; the existing Unity gate becomes the `unity-*` branch. All previously-asserted SKILL strings remain present.

- [ ] **Step 1: Add the failing asserts to `test-skill-phases.sh`**

Insert these lines before `exit $fail` in `plugins/clone-app/tests/test-skill-phases.sh`:

```bash
has "detect-engine.sh"
has "module-contract.md"
has "coverage-report.md"
has "gen-coverage-report.py"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash plugins/clone-app/tests/test-skill-phases.sh`
Expected: FAIL on the four new strings (SKILL.md not yet edited); the pre-existing asserts still PASS.

- [ ] **Step 3: Edit SKILL.md Phase 2**

In `plugins/clone-app/skills/clone-app/SKILL.md`, immediately **before** the line
`### Phase 2a — Unity tool dependency gate (run before dispatch)`, insert:

```markdown
### Phase 2a — Engine dispatch (run before the tool gate)

Classify the package by game engine and load **only** the matching module, so no
engine's tooling docs bloat this orchestrator's context.

```bash
ENGINE="$(bash ${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/detect-engine.sh "$APK")"
# → unity-il2cpp | unity-mono | unreal | godot | native | none
```

- `unity-il2cpp` / `unity-mono` → continue to the Unity tool dependency gate below.
- `unreal` / `godot` → load that engine's guide under
  `${CLAUDE_PLUGIN_ROOT}/skills/clone-app/references/engines/` when its module lands
  (not yet implemented); until then treat as `limited:<engine>-not-implemented`.
- `native` → mechanics `not-recoverable`; generic resource listing only.
- `none` → non-game app; use the standard non-Unity design-capture path.

Whatever engine runs, its module fills the uniform contract in
`${CLAUDE_PLUGIN_ROOT}/skills/clone-app/references/engines/module-contract.md`
(`mechanics-digest.md`, `game-assets/` + `manifest.json`, `netcode-recon.md`, and a
`coverage-report.md` produced by
`python3 ${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/gen-coverage-report.py <manifest.json> --out $WORK/coverage-report.md`).
The downstream build spec reads `coverage-report.md` — never assume full coverage.

```

- [ ] **Step 4: Verify tests pass**

Run: `bash plugins/clone-app/tests/test-skill-phases.sh`
Expected: all PASS (old + four new strings).

- [ ] **Step 5: Commit**

```bash
git add plugins/clone-app/skills/clone-app/SKILL.md plugins/clone-app/tests/test-skill-phases.sh
git commit -m "feat(clone-app): dispatch Phase 2 by game engine"
```

---

### Task 6: Register new files in the structure smoke test + full suite green

**Files:**
- Modify: `plugins/clone-app/tests/smoke-structure.sh`

**Interfaces:**
- Consumes: all files created in Tasks 1–4.
- Produces: smoke test asserts the new scripts/reference exist (+ scripts executable); full `run-all.sh` passes.

- [ ] **Step 1: Add the failing asserts**

In `plugins/clone-app/tests/smoke-structure.sh`, extend the executable-script loop
(line 13) to include the new bash scripts, add the new python script to the
non-exec loop (line 16), and add two `must_exist` lines after line 21:

```bash
# line 13 loop — add: detect-engine.sh setup-extraction-venv.sh
for s in extract-package.sh download-apk.sh resolve-re-scripts.sh detect-unity.sh il2cpp-dump.sh unity-assets.sh detect-engine.sh setup-extraction-venv.sh; do
  must_exist "$P/skills/clone-app/scripts/$s"; must_exec "$P/skills/clone-app/scripts/$s"
done
# line 16 loop — add: gen-coverage-report.py
for s in scrape-play-store.py check-appstore.py extract-design.py extract-logic.py extract-nav-graph.py gen-coverage-report.py; do
  must_exist "$P/skills/clone-app/scripts/$s"
done
# after the references loop:
must_exist "$P/skills/clone-app/scripts/requirements-extraction.txt"
must_exist "$P/skills/clone-app/references/engines/module-contract.md"
```

- [ ] **Step 2: Run smoke to verify it passes**

Run: `bash plugins/clone-app/tests/smoke-structure.sh`
Expected: all PASS (files created in Tasks 1–4 exist + executable).

- [ ] **Step 3: Run the full suite**

Run: `bash plugins/clone-app/tests/run-all.sh`
Expected: `ALL TESTS PASSED` (auto-discovers the new `test-*.sh`/`test-*.py`).

- [ ] **Step 4: Verify upstream untouched**

Run: `git status --porcelain plugins/android-reverse-engineering/`
Expected: prints nothing.

- [ ] **Step 5: Commit**

```bash
git add plugins/clone-app/tests/smoke-structure.sh
git commit -m "test(clone-app): register engine-core files in smoke test"
```

---

## Self-Review

**Spec coverage:**
- Engine-agnostic dispatcher core → Task 1 (`detect-engine.sh`) + Task 5 (SKILL wiring). ✓
- Uniform module contract → Task 4 (`module-contract.md`). ✓
- Coverage manifest + `coverage-report.md` generator → Task 2. ✓
- Isolated extraction venv, stdlib-only core preserved → Task 3. ✓
- `references/engines/` + `scripts/engines/` layout → `references/engines/` created in Task 4; `scripts/engines/` is created by the first per-engine module (separate plan) — noted, not needed for the core to be testable.
- Honest coverage / no silent truncation → Task 2 rollup + Task 4 stance. ✓
- Tests/fixtures scaffold → each task ships its test; Task 6 integrates. ✓
- Per-engine module internals (Unity/Godot/Unreal), Layer-2 Ghidra, Frida seam → **out of scope for this plan** (separate per-engine plans, per the spec's decomposition). ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code. The `scripts/engines/` directory is intentionally deferred to the first engine module (documented above), not a placeholder in this plan.

**Type consistency:** Engine tokens `unity-il2cpp|unity-mono|unreal|godot|native|none` are identical in Task 1 impl, Task 1 test, and Task 5 SKILL text. Manifest keys (`engine`, `assets.expected`, `assets.extracted`, `assets.by_type`, `mechanics[].confidence`, `notes`) match between Task 2 impl, Task 2 test, and Task 4 contract doc. Confidence values `observed|inferred|signature-only|not-recoverable` match between Task 2 and Task 4.

## Next plans (not this one)

Per the spec's decomposition, subsequent plans — one each — implement the per-engine modules under `scripts/engines/<engine>/`: **Unity** (swap AssetRipper stub for UnityPy + Layer-2 Ghidra), **Godot** (`gdsdecomp`), **Unreal** (`CUE4Parse`). Each fills the contract this core defines.
