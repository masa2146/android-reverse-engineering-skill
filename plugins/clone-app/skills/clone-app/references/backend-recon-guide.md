# Backend Recon Guide

The APK is the client. Server-side code is NOT in it. `backend-recon.md` INFERS a
backend design from the observed API contract so a fresh session can rebuild the
backend — it is a design target, not recovered server code. Every inference is
confidence-stamped.

## Input

`$WORK/extracted/payloads.json` (deepened to full Tier-2 in the fidelity pass) +
`$WORK/extracted/re-digest.md` (hosts, auth model, BuildConfig).

## `backend-recon.md` sections

```
# Backend Recon — <pkg>
## Entities         from request/response bodies: each object → table + fields +
                    inferred types; mark which are observed vs guessed
## Relationships    foreign keys / nesting inferred from payload shapes
## Endpoints        per endpoint: method, path, auth, what it reads/writes,
                    inferred server-side validation and side effects
## Auth model       token type, header, refresh flow (from auth payloads)
## Confidence       high = directly observed in payloads; med = inferred from
                    naming/shape; low = guessed, needs runtime confirmation
```

## Rules

- Never present an inference as fact. Tag every entity/rule high/med/low.
- Prefer "observed in `POST /v1/auth/login` response" citations over assertions.
- Where the contract is silent (e.g. server-only business rules), say
  "not observable statically — confirm via dynamic analysis (Phase B)".
