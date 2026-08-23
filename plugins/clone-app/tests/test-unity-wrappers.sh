#!/usr/bin/env bash
# Wrapper contracts for the Unity tooling. unity-assets.sh now really extracts
# (UnityPy under the opt-in venv), so the tool-missing path asserted here is the
# venv, not AssetRipper — AssetRipper is an optional supplement only.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
S="$HERE/../skills/clone-app/scripts"
fail=0
check() {
  local desc="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then echo "PASS: $desc"
  else echo "FAIL: $desc — expected '$expected' got '$actual'"; fail=1; fi
}
has() { grep -q "$1" <<<"$2" && echo "PASS: $3" || { echo "FAIL: $3"; fail=1; }; }

# usage errors → exit 2
bash "$S/il2cpp-dump.sh" >/dev/null 2>&1; check "il2cpp usage" "2" "$?"
bash "$S/unity-assets.sh" >/dev/null 2>&1; check "assets usage" "2" "$?"

# missing package → exit 2, before any venv work
err="$(bash "$S/unity-assets.sh" /no/such/app.apk /tmp/out-$$ 2>&1 >/dev/null)"; rc=$?
check "assets missing package exit 2" "2" "$rc"
has "package not found" "$err" "assets missing-package message"

# il2cpp tool missing → exit 3 + guidance
err="$(IL2CPP_INSPECTOR_CLI=/no/such/bin bash "$S/il2cpp-dump.sh" a b c 2>&1 >/dev/null)"; rc=$?
check "il2cpp missing exit 3" "3" "$rc"
has "Il2CppInspectorRedux" "$err" "il2cpp guidance"

# UnityPy unavailable → exit 3 + venv guidance (never a silent success)
tmp="$(mktemp -d)"; : > "$tmp/fake.apk"
err="$(CLONE_APP_EXTRACTION_PYTHON=/usr/bin/false EXTRACTION_VENV="$tmp/nope" \
       bash "$S/unity-assets.sh" "$tmp/fake.apk" "$tmp/out" 2>&1 >/dev/null)"; rc=$?
check "assets no-UnityPy exit 3" "3" "$rc"
has "setup-extraction-venv.sh" "$err" "assets venv guidance"
has "AssetRipper is NOT required" "$err" "assets states AssetRipper is optional"
rm -rf "$tmp"

# the extractor itself must refuse a non-Unity package rather than fake output
tmp="$(mktemp -d)"
python3 -c "
import zipfile,sys
z=zipfile.ZipFile('$tmp/plain.apk','w'); z.writestr('classes.dex','x'); z.close()"
out="$(python3 "$S/unity-extract.py" "$tmp/plain.apk" --out "$tmp/out" --quiet 2>&1)"; rc=$?
if [[ "$rc" == "3" ]]; then
  echo "SKIP: UnityPy absent — extractor no-Unity-data assertion skipped"
else
  check "extractor rejects non-Unity package" "4" "$rc"
  has "no assets/bin/Data" "$out" "extractor explains why"
fi
rm -rf "$tmp"

# the shipped Unity importer template must exist and be self-contained
[[ -f "$S/templates/ImportExtracted.cs" ]] && echo "PASS: importer template present" \
  || { echo "FAIL: importer template missing"; fail=1; }
has "Tools/Clone App/Import Extracted Assets" "$(cat "$S/templates/ImportExtracted.cs")" \
  "importer exposes its menu item"

exit $fail
