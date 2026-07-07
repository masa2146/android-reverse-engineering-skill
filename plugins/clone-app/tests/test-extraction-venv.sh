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
