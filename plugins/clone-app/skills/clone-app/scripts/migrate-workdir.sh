#!/usr/bin/env bash
# Move a flat pre-layout working directory into deliverables/ extracted/ raw/.
#
# Moves, never copies or deletes: anything unrecognised is left where it is and
# reported, so a migration can never lose work.
#
#   migrate-workdir.sh <workdir> [--dry-run]
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${1:-}"; DRY=0
[[ "${2:-}" == "--dry-run" ]] && DRY=1

if [[ -z "$WORK" || ! -d "$WORK" ]]; then
  echo "ERROR: usage: migrate-workdir.sh <workdir> [--dry-run]" >&2
  exit 2
fi
if [[ -d "$WORK/deliverables" && -d "$WORK/extracted" && -d "$WORK/raw" ]]; then
  echo "already migrated: $WORK"
  exit 0
fi

moved=0; left=0
move() {  # move <src-basename> <dest-relative-dir>
  local src="$WORK/$1" dest="$WORK/$2"
  [[ -e "$src" ]] || return 0
  if [[ "$DRY" == "1" ]]; then echo "  $1 -> $2/"; moved=$((moved+1)); return 0; fi
  mkdir -p "$dest"
  mv "$src" "$dest/" 2>/dev/null && moved=$((moved+1)) || echo "  WARN could not move $1" >&2
}

echo "migrating $WORK"

# deliverables — reports and the reconstruction package
shopt -s nullglob
for f in "$WORK"/clone-report-*.md "$WORK"/fidelity-report-*.md; do
  move "$(basename "$f")" deliverables
done
shopt -u nullglob
move clone-build-spec.md deliverables
move reconstruction        deliverables
move game-flow.md          deliverables

# extracted — clean structured data
move game-assets       extracted
move assets            extracted/game-assets-legacy   # pre-layout extraction dir
move api-surface.json  extracted
move api-surface.md    extracted
move re-digest.md      extracted
move re-summary.txt    extracted
move payloads.json     extracted
move design-tokens.json extracted
move design-digest.md  extracted
move unity-digest.md   extracted
move nav-graph.json    extracted
move logic-signals.json extracted
move logic-digest.md   extracted
move backend-recon.md  extracted
move coverage-report.md extracted
move il2cpp-classes.md extracted
move play.json         extracted/store
move appstore.json     extracted/store
move screenshots       extracted/store

# raw — regenerable
shopt -s nullglob
for f in "$WORK"/*.apk "$WORK"/*.xapk; do
  move "$(basename "$f")" raw/package
done
shopt -u nullglob
move split              raw/package
move output             raw/decompiled
move unity              raw/unity-work
move unity-work         raw/unity-work
move _unity-work        raw/unity-work
move merged             raw/unity-work
move unity-out          raw/il2cpp
move unitycfg           raw/il2cpp
move managed            raw/il2cpp
move il2cpp             raw/il2cpp
move il2cpp-strings.txt raw/il2cpp

if [[ "$DRY" != "1" ]]; then
  PKG="$(basename "$WORK")"
  ROOT="$(dirname "$WORK")"
  bash "$HERE/init-workdir.sh" "$PKG" "$ROOT" >/dev/null
fi

# report anything left at the top level
echo "left in place (unrecognised):"
for e in "$WORK"/*; do
  b="$(basename "$e")"
  case "$b" in deliverables|extracted|raw|README.md) continue ;; esac
  echo "  $b"; left=$((left+1))
done
[[ "$left" -eq 0 ]] && echo "  (none)"

echo "moved $moved item(s)$([[ "$DRY" == "1" ]] && echo ' (dry run)')"
