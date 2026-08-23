#!/usr/bin/env bash
# Create the standard three-layer working directory and its README.
#
#   deliverables/   what a human reads
#   extracted/      clean data a machine reads
#   raw/            regenerable intermediates — safe to delete
#
# Idempotent: re-running refreshes README.md and leaves existing content alone.
# Prints the working dir on success.
set -uo pipefail

PKG="${1:-}"; ROOT="${2:-./work}"
if [[ -z "$PKG" ]]; then
  echo "ERROR: usage: init-workdir.sh <package> [root]" >&2
  exit 2
fi

WORK="$ROOT/$PKG"
mkdir -p "$WORK"/deliverables \
         "$WORK"/extracted/store \
         "$WORK"/raw/package "$WORK"/raw/decompiled "$WORK"/raw/unity-work "$WORK"/raw/il2cpp || {
  echo "ERROR: could not create $WORK" >&2; exit 1; }

cat > "$WORK/README.md" <<MD
# $PKG — working directory

Three layers, by what you do with them.

| Layer | Contents | Keep? |
|---|---|---|
| **deliverables/** | reports, build spec, reconstruction package — the things written for a person to read | yes |
| **extracted/** | clean structured data: game assets, API surface, RE digests, store metrics | yes |
| **raw/** | package, decompiled sources, unpack scratch — all regenerable | delete when done |

Start at \`deliverables/\`. Everything there cites \`extracted/\`; nothing cites \`raw/\`.

## deliverables/
| File | What it is |
|---|---|
| \`clone-report-<date>.md\` | feasibility: stack, effort, infra cost, market, verdict |
| \`fidelity-report-<date>.md\` | deep pass: full API surface, in-app logic, backend design |
| \`clone-build-spec.md\` | the spec a build session works from |
| \`reconstruction/\` | games only: architecture, mechanics, runtime flow, meta design, unknowns, code skeleton |

## extracted/
| Path | What it is |
|---|---|
| \`game-assets/\` | entities, textures, sprites, meshes, levels, shaders, particles, animations, audio, fonts, UI, project settings — see its own \`IMPORT.md\` |
| \`api-surface.json\` / \`.md\` | every type, field, property and method name (IL2CPP metadata). **Multi-megabyte — query it, do not open it.** |
| \`re-digest.md\`, \`payloads.json\`, \`re-summary.txt\` | endpoints, hosts, auth, SDKs |
| \`design-tokens.json\`, \`nav-graph.json\`, \`logic-signals.json\` | non-game apps |
| \`coverage-report.md\` | honest covered / partial / missing rollup |
| \`store/\` | \`play.json\`, \`appstore.json\`, \`screenshots/\` |

## raw/
| Path | Size order | Regenerate with |
|---|---|---|
| \`package/\` | the downloaded APK/XAPK and its splits | \`download-apk.sh\` |
| \`decompiled/\` | jadx output | \`decompile.sh\` |
| \`unity-work/\` | unpacked + merged Unity serialized files | \`unity-assets.sh\` |
| \`il2cpp/\` | \`global-metadata.dat\`, strings dump | unzip from the package |

Nothing here is deleted automatically — Phases 8 and 9 read back from
\`decompiled/\`. Clear it yourself when finished:

\`\`\`bash
bash <scripts>/clean-workdir.sh "$WORK"
\`\`\`

## Legal
Extracted content is reference material. The transferable output is structure —
architecture, mechanics, schema, physics constants, taxonomy.
MD

echo "$WORK"
