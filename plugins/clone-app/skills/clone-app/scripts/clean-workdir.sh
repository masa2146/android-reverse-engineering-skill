#!/usr/bin/env bash
# Delete the regenerable raw/ layer of a working directory. Never touches
# deliverables/ or extracted/. Nothing in the pipeline calls this — Phases 8
# and 9 read back from raw/decompiled, so removal is always the user's move.
#
#   clean-workdir.sh <workdir> [--dry-run] [--yes]
set -uo pipefail

WORK="${1:-}"; shift || true
DRY=0; ASSUME_YES=0
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --yes|-y)  ASSUME_YES=1 ;;
    *) echo "ERROR: unknown flag $a" >&2; exit 2 ;;
  esac
done

if [[ -z "$WORK" ]]; then
  echo "ERROR: usage: clean-workdir.sh <workdir> [--dry-run] [--yes]" >&2
  exit 2
fi
if [[ ! -d "$WORK" ]]; then
  echo "ERROR: not a directory: $WORK" >&2
  exit 2
fi
if [[ ! -d "$WORK/raw" ]]; then
  echo "nothing to clean: $WORK/raw does not exist"
  exit 0
fi

size="$(du -sh "$WORK/raw" 2>/dev/null | cut -f1)"
echo "raw/ holds $size in $WORK"
du -sh "$WORK"/raw/*/ 2>/dev/null | sed 's/^/  /'

if [[ "$DRY" == "1" ]]; then
  echo "(dry run — nothing deleted)"
  exit 0
fi
if [[ "$ASSUME_YES" != "1" ]]; then
  printf 'delete %s/raw ? [y/N] ' "$WORK"
  read -r reply
  [[ "$reply" == "y" || "$reply" == "Y" ]] || { echo "aborted"; exit 0; }
fi

rm -rf "${WORK:?}/raw"
echo "removed $WORK/raw — freed $size. deliverables/ and extracted/ untouched."
