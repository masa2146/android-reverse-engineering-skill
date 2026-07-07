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
