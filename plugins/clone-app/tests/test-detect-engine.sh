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
