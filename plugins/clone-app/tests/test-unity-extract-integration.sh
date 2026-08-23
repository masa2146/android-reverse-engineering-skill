#!/usr/bin/env bash
# End-to-end extraction against a real package. Opt-in: skips cleanly unless
# CLONE_APP_SAMPLE_APK points at an APK/XAPK. Everything else in the suite is
# offline; this is the only test that touches a real game.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
S="$HERE/../skills/clone-app/scripts"
fail=0
check() { if [[ -n "$2" ]]; then echo "PASS: $1"; else echo "FAIL: $1"; fail=1; fi; }

if [[ -z "${CLONE_APP_SAMPLE_APK:-}" ]]; then
  echo "SKIP: set CLONE_APP_SAMPLE_APK=/path/to/app.xapk to run the integration test"
  exit 0
fi
if [[ ! -f "$CLONE_APP_SAMPLE_APK" ]]; then
  echo "FAIL: CLONE_APP_SAMPLE_APK not found: $CLONE_APP_SAMPLE_APK"; exit 1
fi

OUT="$(mktemp -d)/game-assets"
bash "$S/unity-assets.sh" "$CLONE_APP_SAMPLE_APK" "$OUT" >/dev/null 2>&1
rc=$?
if [[ "$rc" -eq 3 ]]; then echo "SKIP: extraction venv unavailable"; exit 0; fi
[[ "$rc" -eq 0 ]] && echo "PASS: extraction exits 0" || { echo "FAIL: exit $rc"; exit 1; }

for f in manifest.json IMPORT.md ARCHITECTURE.md materials.json physics.json \
         shaders/README.md project-settings/README.md unity-import/ImportExtracted.cs; do
  [[ -s "$OUT/$f" ]] && echo "PASS: $f written" || { echo "FAIL: $f missing/empty"; fail=1; }
done
for d in entities textures sprites meshes audio fonts levels scenes animations \
         particles shaders ui project-settings; do
  [[ -d "$OUT/$d" ]] && echo "PASS: $d/ present" || { echo "FAIL: $d/ missing"; fail=1; }
done

# The manifest must never claim more than exists on disk.
python3 - "$OUT" <<'PY'
import json, os, sys
out = sys.argv[1]
m = json.load(open(os.path.join(out, "manifest.json")))
on_disk = sum(len(fs) for _, _, fs in os.walk(out))
claimed = m["assets"]["extracted"]
print(("PASS" if claimed <= on_disk else "FAIL")
      + f": manifest claims {claimed} <= {on_disk} files on disk")
sys.exit(0 if claimed <= on_disk else 1)
PY
[[ $? -eq 0 ]] || fail=1

# At least one entity folder must be genuinely self-contained.
python3 - "$OUT" <<'PY'
import json, os, sys
out = sys.argv[1]
root = os.path.join(out, "entities")
ok = 0
for name in os.listdir(root):
    d = os.path.join(root, name)
    if not os.path.isdir(d):
        continue
    j = os.path.join(d, "entity.json")
    if not os.path.exists(j):
        continue
    files = set(os.listdir(d))
    if any(f.endswith(".obj") for f in files) and "textures" in files and "README.md" in files:
        ok += 1
print(("PASS" if ok else "FAIL") + f": {ok} self-contained entity folders")
sys.exit(0 if ok else 1)
PY
[[ $? -eq 0 ]] || fail=1

rm -rf "$(dirname "$OUT")"
exit $fail
