#!/usr/bin/env bash
# Classify an APK/XAPK as a Unity build: il2cpp | mono | none.
# Handles XAPK bundles by also scanning nested base.apk / split apks.
set -uo pipefail

APK="${1:-}"
if [[ -z "$APK" || ! -f "$APK" ]]; then
  echo "ERROR: usage: detect-unity.sh <apk-or-xapk>" >&2
  exit 2
fi

listing="$(unzip -Z1 "$APK" 2>/dev/null)" || {
  echo "ERROR: cannot read zip: $APK" >&2; exit 2; }

# XAPK: top-level *.apk entries are inner packages — scan their contents too.
nested_apks="$(grep -E '\.apk$' <<<"$listing" || true)"
if [[ -n "$nested_apks" ]]; then
  INNER_TMP="$(mktemp -d)"
  trap 'rm -rf "$INNER_TMP"' EXIT
  while IFS= read -r inner; do
    [[ -z "$inner" ]] && continue
    inner_path="$INNER_TMP/$(basename "$inner")"
    unzip -p "$APK" "$inner" > "$inner_path" 2>/dev/null || continue
    inner_listing="$(unzip -Z1 "$inner_path" 2>/dev/null || true)"
    listing="$listing"$'\n'"$inner_listing"
  done <<<"$nested_apks"
fi

if grep -q 'global-metadata\.dat' <<<"$listing" \
   && grep -qi 'libil2cpp\.so' <<<"$listing"; then
  echo il2cpp; exit 0
fi
# Mono: a real managed assembly is a DIRECT child of Managed/ (e.g.
# Assembly-CSharp.dll). Anchor to end-of-line so Managed/Resources/*-resources.dat
# resource stubs (IL2CPP builds) don't false-match as mono. The [^/]+ forbids
# matching into the Resources/ subdir.
if grep -Eq 'assets/bin/Data/Managed/[^/]+\.dll$' <<<"$listing"; then
  echo mono; exit 0
fi
echo none
exit 0
