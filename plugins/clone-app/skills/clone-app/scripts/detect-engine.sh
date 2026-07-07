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
