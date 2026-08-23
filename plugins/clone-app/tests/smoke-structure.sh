#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"   # repo root
P="$ROOT/plugins/clone-app"
fail=0
must_exist() { [[ -e "$1" ]] && echo "PASS exists: ${1#$ROOT/}" || { echo "FAIL missing: ${1#$ROOT/}"; fail=1; }; }
must_exec()  { [[ -x "$1" ]] && echo "PASS exec: ${1#$ROOT/}"   || { echo "FAIL not exec: ${1#$ROOT/}"; fail=1; }; }

must_exist "$P/.claude-plugin/plugin.json"
must_exist "$P/skills/clone-app/SKILL.md"
must_exist "$P/commands/clone-app.md"
must_exist "$P/README.md"
for s in extract-package.sh download-apk.sh resolve-re-scripts.sh detect-unity.sh il2cpp-dump.sh unity-assets.sh detect-engine.sh setup-extraction-venv.sh; do
  must_exist "$P/skills/clone-app/scripts/$s"; must_exec "$P/skills/clone-app/scripts/$s"
done
for s in scrape-play-store.py check-appstore.py extract-design.py extract-logic.py extract-nav-graph.py gen-coverage-report.py unity-extract.py render-mesh-preview.py; do
  must_exist "$P/skills/clone-app/scripts/$s"
done
for r in stack-recommendation-guide effort-estimation-guide infra-cost-guide report-template re-digest-contract design-capture-guide unity-re-guide unity-asset-extraction-guide clone-build-spec-template fidelity-pass-guide logic-capture-guide backend-recon-guide; do
  must_exist "$P/skills/clone-app/references/$r.md"
done
must_exist "$P/skills/clone-app/scripts/requirements-extraction.txt"
must_exist "$P/skills/clone-app/references/engines/module-contract.md"
must_exist "$P/skills/clone-app/scripts/templates/ImportExtracted.cs"
must_exist "$P/tests/fixtures/unity-sample/cube.obj"
must_exist "$P/tests/fixtures/unity-sample/level-001-a.json"

# JSON validity
python3 -c "import json;json.load(open('$P/.claude-plugin/plugin.json'));json.load(open('$ROOT/.claude-plugin/marketplace.json'))" \
  && echo "PASS json valid" || { echo "FAIL json invalid"; fail=1; }

# clone-app present in marketplace
python3 -c "
import json;d=json.load(open('$ROOT/.claude-plugin/marketplace.json'))
names=[p['name'] for p in d['plugins']]
assert 'clone-app' in names and 'android-reverse-engineering' in names
print('PASS marketplace has both plugins')" || { echo "FAIL marketplace entries"; fail=1; }

exit $fail
