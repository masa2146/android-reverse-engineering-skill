# Clone Build Spec — {APP_TITLE}

> The standalone build contract. A fresh session with only this file and the
> `$WORK/` artifacts it references must be able to build a pixel-perfect,
> production-ready clone. Reference every artifact by **absolute path + summary**.

**Package:** {PACKAGE}  ·  **Date:** {DATE}  ·  **Selected stack:** {STACK}

## 1. Product overview & parity target
What the app does; the parity bar (pixel-perfect visual + feature-complete).

## 2. Design system
From `$WORK/extracted/design-tokens.json` (confidence: {…}): color palette + roles, type
scale (fonts + sizes), spacing scale, corner radii, light/dark theme. Note where
confidence is med/low and screenshots are the source of truth.

## 3. Screen-by-screen spec
For **each** screen: purpose · layout **component tree** (from native XML) ·
components · states (empty/loading/error) · navigation in/out · the screen's
logic (cross-ref `$WORK/extracted/logic-digest.md`) · matching screenshot
(`$WORK/extracted/store/screenshots/NN.png`).

## 3b. User-flow diagrams
Step-by-step flows (onboarding, core loop, payment) from `$WORK/extracted/logic-digest.md`:
each step's screen, the action that advances it, and the API call it triggers.

## 4. Navigation map / IA
The full screen graph + entry points, generated from `$WORK/extracted/nav-graph.json`
(nodes = screens, edges = transitions + triggers) — not inferred.

## 5. API contract
From `$WORK/extracted/payloads.json`: per endpoint — host, method, path, auth,
request body, response shape, headers.

## 5b. Backend rebuild spec
The from-scratch backend design from `$WORK/extracted/backend-recon.md`: per-endpoint
behavior, auth flow, inferred server-side validation. Confidence-stamped — this
is a rebuild target, not recovered server code.

## 6. Data model
Entities, fields, relationships from `$WORK/extracted/backend-recon.md` (observed vs
inferred, each confidence-stamped).

## 7. Asset inventory
Icons, fonts, drawables — extract from `$WORK/raw/decompiled` or recreate. List each.

## 8. Acceptance criteria
Per screen and per flow — the testable definition of done for prod quality.

## 9. Out of scope / assumptions
Explicit exclusions and assumptions.

## 10. Artifact references
Absolute paths to: `design-tokens.json`, `design-digest.md`, `screenshots/`,
`payloads.json`, `re-digest.md` (+ `unity-digest.md`, `game-assets/` if Unity).

---

## Game variant (Unity)
Replace these sections:
- **§2 Design system** → art style + UI atlas inventory; palette from sprites.
- **§3 Screen-by-screen** → **scene/prefab-by-scene** spec (from `unity-digest.md`):
  each scene's objects, UI canvas, transitions; matching screenshot;
  + game rules / formulas (from `unity-digest.md`).
- **§5 API contract** → **netcode**: backend (Photon/PlayFab/Mirror/custom),
  message types, sync model (from the IL2CPP/Mono type model).
- **§7 Asset inventory** → `$WORK/extracted/game-assets/` manifest (sprites, atlases,
  audio, shaders, scenes, prefabs) + the AssetRipper project path.
