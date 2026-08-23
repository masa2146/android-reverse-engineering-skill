#!/usr/bin/env bash
# init / clean / migrate: the three-layer working directory.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
S="$HERE/../skills/clone-app/scripts"
fail=0
check() { if [[ "$2" == "$3" ]]; then echo "PASS: $1"; else echo "FAIL: $1 — expected '$2' got '$3'"; fail=1; fi; }
ok()    { if eval "$2"; then echo "PASS: $1"; else echo "FAIL: $1"; fail=1; fi; }
has()   { grep -q "$1" <<<"$2" && echo "PASS: $3" || { echo "FAIL: $3"; fail=1; }; }

# -- init ------------------------------------------------------------------
bash "$S/init-workdir.sh" >/dev/null 2>&1; check "init usage" "2" "$?"

TMP="$(mktemp -d)"
OUT="$(bash "$S/init-workdir.sh" com.example "$TMP")"
check "init prints the workdir" "$TMP/com.example" "$OUT"
for d in deliverables extracted extracted/store raw raw/package raw/decompiled raw/unity-work raw/il2cpp; do
  ok "init created $d" "[[ -d '$OUT/$d' ]]"
done
ok "init wrote README" "[[ -s '$OUT/README.md' ]]"
readme="$(cat "$OUT/README.md")"
has "com.example" "$readme" "README names the package"
has "deliverables/" "$readme" "README explains deliverables"
has "clean-workdir.sh" "$readme" "README points at the cleanup script"
has "query it, do not open it" "$readme" "README warns about api-surface size"

# idempotent, and existing content survives
echo hello > "$OUT/deliverables/report.md"
bash "$S/init-workdir.sh" com.example "$TMP" >/dev/null
check "init is idempotent" "hello" "$(cat "$OUT/deliverables/report.md")"

# -- clean -----------------------------------------------------------------
bash "$S/clean-workdir.sh" >/dev/null 2>&1; check "clean usage" "2" "$?"
bash "$S/clean-workdir.sh" /no/such/dir >/dev/null 2>&1; check "clean missing dir" "2" "$?"

mkdir -p "$OUT/raw/package"; dd if=/dev/zero of="$OUT/raw/package/app.apk" bs=1024 count=64 2>/dev/null
out="$(bash "$S/clean-workdir.sh" "$OUT" --dry-run)"
check "dry run exits 0" "0" "$?"
has "dry run" "$out" "dry run says so"
ok "dry run deleted nothing" "[[ -f '$OUT/raw/package/app.apk' ]]"

bash "$S/clean-workdir.sh" "$OUT" --yes >/dev/null
ok "clean removed raw/" "[[ ! -d '$OUT/raw' ]]"
ok "clean kept deliverables/" "[[ -f '$OUT/deliverables/report.md' ]]"
ok "clean kept extracted/" "[[ -d '$OUT/extracted' ]]"
bash "$S/clean-workdir.sh" "$OUT" --yes >/dev/null; check "clean is idempotent" "0" "$?"
rm -rf "$TMP"

# -- migrate ---------------------------------------------------------------
TMP="$(mktemp -d)"; W="$TMP/com.flat"; mkdir -p "$W"
: > "$W/app.xapk"
: > "$W/clone-report-2026-01-01.md"
: > "$W/play.json"; : > "$W/appstore.json"
: > "$W/api-surface.json"; : > "$W/re-digest.md"
mkdir -p "$W/game-assets" "$W/output" "$W/unity" "$W/reconstruction" "$W/my-notes"
: > "$W/my-notes/scratch.txt"

out="$(bash "$S/migrate-workdir.sh" "$W" --dry-run)"
has "dry run" "$out" "migrate dry run says so"
ok "migrate dry run moved nothing" "[[ -f '$W/app.xapk' ]]"

out="$(bash "$S/migrate-workdir.sh" "$W")"
ok "report moved"        "[[ -f '$W/deliverables/clone-report-2026-01-01.md' ]]"
ok "reconstruction moved" "[[ -d '$W/deliverables/reconstruction' ]]"
ok "game-assets moved"   "[[ -d '$W/extracted/game-assets' ]]"
ok "api-surface moved"   "[[ -f '$W/extracted/api-surface.json' ]]"
ok "store metrics moved" "[[ -f '$W/extracted/store/play.json' && -f '$W/extracted/store/appstore.json' ]]"
ok "package moved"       "[[ -f '$W/raw/package/app.xapk' ]]"
ok "decompiled moved"    "[[ -d '$W/raw/decompiled' ]]"
ok "unity scratch moved" "[[ -d '$W/raw/unity-work' ]]"
ok "README written"      "[[ -s '$W/README.md' ]]"
ok "unknown dir left in place" "[[ -f '$W/my-notes/scratch.txt' ]]"
has "my-notes" "$out" "migrate reports what it did not recognise"

out="$(bash "$S/migrate-workdir.sh" "$W")"
has "already migrated" "$out" "migrate is idempotent"
rm -rf "$TMP"

exit $fail
