# RE Digest Contract

The Phase 2 subagent runs the reverse-engineering workflow in isolation and
MUST produce these three files under `$WORK/`, then return only the summary.
This file is the single source of truth for their schema. The subagent prompt
points here; do not duplicate the schema into SKILL.md prose.

## File 1 — `$WORK/extracted/re-digest.md` (human-readable, main artifact)

Required section headings, in this order:

```
# RE Digest — <pkg>
## Framework & Stack    framework, HTTP lib, DI, serialization, obfuscation level
## Hosts                first-party vs third-party (table)
## Endpoint Inventory   Tier-1: host | method | path | auth | source file
## Key Flow Payloads    Tier-2: auth, payment/checkout, 1-2 core flows
                        — request body / response shape / headers / params
## BuildConfig Secrets  base URLs, API keys, feature flags, flavors
## Feature Signals      screen count, SDKs, permissions, components
## RE Method            re-skill | direct-scripts | limited: <framework>
```

## File 2 — `$WORK/extracted/payloads.json` (machine-readable, durable memory)

Required top-level keys: `package`, `re_method`, `endpoints`, `buildconfig`.
Each item in `endpoints` has: `host`, `method`, `path`, `auth`, `source`,
`request_body`, `response`, `headers`.

```json
{
  "package": "com.example.app",
  "re_method": "re-skill",
  "endpoints": [
    {
      "host": "api.example.com",
      "method": "POST",
      "path": "/v1/auth/login",
      "auth": "none",
      "source": "com/example/api/AuthApi.java",
      "request_body": { "email": "string", "password": "string" },
      "response": { "token": "string", "user": {} },
      "headers": { "Content-Type": "application/json" }
    }
  ],
  "buildconfig": { "BASE_URL": "https://api.example.com/v1" }
}
```

- `request_body` and `response` are `null` for Tier-1-only endpoints.
- Populate them ONLY for the key flows: **auth, payment/checkout, and the
  1–2 core feature endpoints** (decision Q3=B). Everything else is a Tier-1
  row with `null` payloads. Going Tier-2 on every endpoint is a non-goal —
  it is token-expensive and the RE skill itself warns against it.

## File 3 — `$WORK/extracted/re-summary.txt` (≤40 lines, the only RE text returned)

Plain text. The subagent's return value = the contents of this file plus the
paths to the two files above. Fields:

- framework
- host count (first-party / third-party)
- endpoint count
- key-flow names found (auth / payment / core)
- secrets-found count (BuildConfig)
- RE method: `re-skill` | `direct-scripts` | `limited: <framework>`
- blockers / warnings (e.g. obfuscation, framework guard)

The subagent MUST NOT return raw decompiled sources.

## RE Method values

| Value | Meaning |
|---|---|
| `re-skill` | The `android-reverse-engineering` skill ran the workflow. |
| `direct-scripts` | The skill was absent; the sibling plugin's bash scripts ran. |
| `limited: <framework>` | Flutter / React Native / Cordova / Xamarin — Java decompile is shallow; payloads may be empty and the digest is partial. |

## Framework guard

If the fingerprint reports Flutter / React Native / Cordova / Xamarin, set
`RE Method: limited: <framework>`, write whatever partial signals are
available (manifest, strings, hardcoded URLs, SDK list), and leave payloads
empty where they cannot be recovered. Downstream phases widen the
uncertainty band accordingly.

## Design & Unity outputs (clone-app additions)

Beyond the three RE files, the Phase 2 subagent ALSO writes:

- `$WORK/extracted/design-tokens.json` + `$WORK/extracted/design-digest.md` — from
  `extract-design.py` on the decompile root (standard apps). Schema and
  confidence rules: see `design-capture-guide.md`.
- For Unity builds (`detect-unity.sh` → `il2cpp`/`mono`): `$WORK/extracted/unity-digest.md`
  (C# type model + netcode) and `$WORK/extracted/game-assets/` + `manifest.json` (via
  `il2cpp-dump.sh`/`ilspycmd` + `unity-assets.sh`). See `unity-re-guide.md`.

The subagent returns the short `design-summary` (and `unity-summary` when Unity)
plus these paths — never raw resources, sources, or assets.

### RE Method addition
| Value | Meaning |
|---|---|
| `limited: unity-no-tools` | Unity build but Il2CppInspectorRedux/AssetRipper absent — partial digest, assets/types may be empty. |

## Deep-extraction artifacts (Phase 4 — runs by default)

Phase 4 runs unconditionally, before any gate. Its deep-extraction
subagent reuses `$WORK/raw/decompiled` (no re-decompile) and ALSO writes:

- `$WORK/extracted/logic-digest.md` — in-app logic & workflows, distilled from
  `extract-logic.py`'s signals per `logic-capture-guide.md`.
- `$WORK/extracted/nav-graph.json` — navigation graph from `extract-nav-graph.py`
  (keys: `root`, `framework`, `nodes[]`, `edges[]`).
- `$WORK/extracted/backend-recon.md` — inferred backend design per `backend-recon-guide.md`
  (confidence-stamped; a rebuild target, not recovered server code).

It also **deepens `$WORK/extracted/payloads.json`**: in the fidelity pass, Tier-2
request/response/headers are populated for **every first-party endpoint**, not
just auth/payment/core. This overrides the "Tier-2 on every endpoint is a
non-goal" rule above, which governs ONLY the Phase 2 feasibility pass.
