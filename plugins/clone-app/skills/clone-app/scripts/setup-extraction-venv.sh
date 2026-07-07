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
