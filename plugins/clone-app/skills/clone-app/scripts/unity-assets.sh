#!/usr/bin/env bash
# Extract Unity game assets from an APK/XAPK — meshes, textures, sprites,
# materials, shaders, particles, animations, audio, fonts, levels, scenes,
# prefab structure and project settings — grouped per entity and ready to
# import. See references/unity-asset-extraction-guide.md for the output contract.
#
# The engine is unity-extract.py running under the opt-in extraction venv
# (UnityPy + numpy + Pillow). This replaces the old AssetRipper path: the current
# AssetRipper release is a web-server GUI with no one-shot CLI, so it could never
# extract anything unattended. It stays available as an optional supplement via
# ASSETRIPPER_CLI, never as a prerequisite.
#
# Exit codes: 0 success · 2 usage · 3 venv/UnityPy unavailable · 4 extraction failed.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

APK="${1:-}"; OUT="${2:-}"
if [[ -z "$APK" || -z "$OUT" ]]; then
  echo "ERROR: usage: unity-assets.sh <apk-or-xapk> <out-dir>" >&2
  exit 2
fi
if [[ ! -e "$APK" ]]; then
  echo "ERROR: package not found: $APK" >&2
  exit 2
fi

# Resolve a python that has UnityPy: an explicit override, the extraction venv,
# or build the venv now.
PY="${CLONE_APP_EXTRACTION_PYTHON:-}"
if [[ -z "$PY" ]]; then
  VENV="${EXTRACTION_VENV:-$HERE/../.venv-extraction}"
  if [[ -x "$VENV/bin/python" ]]; then
    PY="$VENV/bin/python"
  else
    echo "INFO: extraction venv missing — creating it (UnityPy, numpy, Pillow)…" >&2
    if VENV_PATH="$(bash "$HERE/setup-extraction-venv.sh" 2>/dev/null)"; then
      PY="$VENV_PATH/bin/python"
    fi
  fi
fi

if [[ -z "$PY" ]] || ! "$PY" -c "import UnityPy" >/dev/null 2>&1; then
  cat >&2 <<'EOF'
ERROR: UnityPy is not available, so no assets can be extracted.
Create the opt-in extraction venv:
    bash skills/clone-app/scripts/setup-extraction-venv.sh
It installs UnityPy (assets), numpy + Pillow (mesh previews) into
skills/clone-app/.venv-extraction — nothing is added to the system python.
Offline? Point CLONE_APP_EXTRACTION_PYTHON at a python that already has UnityPy.
AssetRipper is NOT required; it is an optional supplement only.
EOF
  exit 3
fi

mkdir -p "$OUT"

EXTRA_ARGS=()
[[ "${UNITY_ASSETS_NO_PREVIEWS:-0}" == "1" ]] && EXTRA_ARGS+=(--no-previews)
# Scratch goes in the workdir's raw/ layer when <out> sits under one; the
# extractor works this out itself, UNITY_ASSETS_WORK only overrides it.
[[ -n "${UNITY_ASSETS_WORK:-}" ]] && EXTRA_ARGS+=(--work "$UNITY_ASSETS_WORK")

"$PY" "$HERE/unity-extract.py" "$APK" --out "$OUT" "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"
rc=$?
if [[ "$rc" -eq 3 ]]; then
  echo "ERROR: UnityPy import failed inside the extraction venv." >&2
  exit 3
fi
if [[ "$rc" -ne 0 ]]; then
  echo "ERROR: unity-extract.py failed (exit $rc)." >&2
  exit 4
fi

if [[ ! -s "$OUT/manifest.json" ]]; then
  echo "ERROR: extraction produced no manifest.json — treating as failure." >&2
  exit 4
fi

# Optional supplement: AssetRipper can add scene/shader reconstruction UnityPy
# does not attempt. Never required, never fabricated.
BIN="${ASSETRIPPER_CLI:-}"
if [[ -n "$BIN" ]] && command -v "$BIN" >/dev/null 2>&1; then
  cat > "$OUT/assetripper-supplement.md" <<EOF
# Optional AssetRipper supplement
UnityPy extraction already completed (see manifest.json). AssetRipper is present
at: $BIN
Its current release is a web-server GUI with no one-shot CLI, so run it by hand
if you want its scene/shader reconstruction on top of this extraction:
  1. $BIN
  2. open the printed URL, load: $APK
  3. export alongside: $OUT
EOF
fi

echo "$OUT"
