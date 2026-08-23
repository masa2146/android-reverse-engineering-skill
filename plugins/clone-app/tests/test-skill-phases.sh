#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SKILL="$HERE/../skills/clone-app/SKILL.md"
fail=0
has() {
  if grep -qF "$1" "$SKILL"; then echo "PASS: SKILL has '$1'"
  else echo "FAIL: SKILL missing '$1'"; fail=1; fi
}

has "extract-design.py"
has "detect-unity.sh"
has "il2cpp-dump.sh"
has "unity-assets.sh"
has "design-tokens.json"
has "screenshots/"
has "## Phase 8"
has "clone-build-spec.md"
has "clone-build-spec-template.md"
has "unity-re-guide.md"
has "design-capture-guide.md"
has "extract-logic.py"
has "extract-nav-graph.py"
has "logic-digest.md"
has "nav-graph.json"
has "backend-recon.md"
has "fidelity-report-"
has "fidelity-pass-guide.md"
has "detect-engine.sh"
has "module-contract.md"
has "coverage-report.md"
has "gen-coverage-report.py"
has "il2cpp-metadata-dump.py"
has "api-surface.json"
has "## Phase 9"
has "game-reconstruction-guide.md"
has "reconstruction/"
has "Never read \`api-surface.md\`"

exit $fail
