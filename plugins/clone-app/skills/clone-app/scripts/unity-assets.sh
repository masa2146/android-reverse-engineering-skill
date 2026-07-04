#!/usr/bin/env bash
# Extract Unity game assets (textures, sprites, audio, scenes, prefabs) from an
# APK via AssetRipper. Only the tool-missing path + usage errors are exercised by
# tests (test-unity-wrappers.sh).
#
# REALITY (verified against AssetRipper 1.3.14, "AssetRipper.GUI.Free", 2026-07):
# the current release is a WEB-SERVER GUI, not a console converter. Its flags are
# --headless / --port / --log — there is NO one-shot `<input> -o <out>` mode, and
# the web API it serves has no discoverable, stable spec (Swagger shell loads but
# the OpenAPI JSON is absent; /api/* guesses 404). Driving it blind is not robust,
# so this wrapper does NOT fake a conversion. Instead it:
#   - exits 3 with install guidance if the binary is absent, or
#   - if the binary is present, either guides the user to run the GUI manually, or
#     (with UNITY_ASSETS_MANUAL=1) records a "manual export needed" marker and
#     exits 0 so the pipeline can degrade gracefully.
set -uo pipefail

APK="${1:-}"; OUT="${2:-}"
if [[ -z "$APK" || -z "$OUT" ]]; then
  echo "ERROR: usage: unity-assets.sh <apk> <out-dir>" >&2
  exit 2
fi

BIN="${ASSETRIPPER_CLI:-AssetRipper}"
if ! command -v "$BIN" >/dev/null 2>&1; then
  cat >&2 <<'EOF'
ERROR: AssetRipper CLI not found.
Install it (needs the .NET runtime): https://github.com/AssetRipper/AssetRipper
Put the binary on PATH, or set ASSETRIPPER_CLI=/path/to/AssetRipper.GUI.Free.
EOF
  exit 3
fi

mkdir -p "$OUT"

# AssetRipper GUI.Free is a web-server app with no one-shot CLI conversion. We do
# not fake a conversion. Either the user runs the GUI, or opts into manual-defer.
if [[ "${UNITY_ASSETS_MANUAL:-0}" == "1" ]]; then
  cat > "$OUT/manual-export-needed.md" <<EOF
# AssetRipper export deferred (manual)
AssetRipper GUI.Free is a web-server app with no one-shot CLI. To extract assets:
  1. Run: $BIN
  2. Open the printed URL in a browser
  3. Load: $APK
  4. Export to: $OUT
Source APK: $APK
EOF
  echo "DEFERRED: AssetRipper GUI run needed; marker at $OUT/manual-export-needed.md"
  exit 0
fi

cat >&2 <<EOF
ERROR: AssetRipper GUI.Free (current release) is a web-server app, not a console
converter — no one-shot '<input> -o <out>' mode, and its web API is not documented
enough to drive. This wrapper will not fake an extraction. Either:
  (a) run the GUI manually:  $BIN   # then load $APK, export to $OUT
  (b) re-run with UNITY_ASSETS_MANUAL=1 to defer (writes a marker, exits 0)
EOF
exit 4
