# Clone Feasibility Report — {APP_TITLE}

**Package:** {PACKAGE}
**Date:** {DATE}
**Analyzed by:** clone-app skill

## 1. App Overview
- Title / developer / category / installs / rating ({RATING} from {RATING_COUNT} reviews)
- iOS App Store presence: {YES/NO + link}
- One-paragraph description of what the app does.

## 2. Tech Stack (Detected)
- Mobile framework: {framework} (RE fingerprint marker: {marker})
- HTTP stack: {Retrofit/Ktor/...}
- Backend signals: {first-party hosts, REST/GraphQL/WS}
- Notable SDKs: {list}
- Obfuscation level: {low/med/high} — analysis completeness caveat if high.

## 3. Recommended Clone Stack
- Selected by user: {stack}
- Rationale: {1-2 lines}

## 4. Feature List (from APK)
- Screens: {n}
- API endpoints: {n} (key ones listed)
- Integrations: {list}
- Backend required: {yes/no + why}

## 4a. Design System (Detected)
- Palette: {key colors} · Type: {fonts + scale} · Theme: {light/dark}
- Confidence: {high/med/low} (source: APK res + {n} Play screenshots)
- Full tokens: `$WORK/design-tokens.json`; screenshots: `$WORK/screenshots/`

## 4b. Game Content (if a game engine was detected)
Source: `$WORK/game-assets/` — see its `manifest.json`, `coverage-report.md` and
`IMPORT.md`. Omit this section entirely for non-game apps.

- **Build type:** {il2cpp/mono} · Type model: `$WORK/unity-digest.md`
- **Extracted:** {n} entities · {n} meshes ({n} fracture pieces) · {n} textures
  ({n} lossless / {n} decoded from compressed) · {n} sprites ({n} with 9-slice
  borders) · {n} materials · {n} shaders · {n} particle systems ·
  {n} animation clips + {n} controllers · {n} audio · {n} fonts · {n} levels ·
  {n} UI canvases · {n} scenes
- **Level design data:** {n} levels, {n} distinct entities, mechanic-introduction
  curve in `levels/level-analysis.json`{, note A/B ladders if duplicate ids exist}
- **Engine settings that differ from defaults:** {from
  `project-settings/README.md` — gravity, solver iterations, fixed timestep, …}.
  These are the tuning constants a clone would otherwise guess.
- **Shaders:** {n} built-in · {n} commercial ({name the packages to buy}) ·
  {n} custom to this game (must be re-authored from the recorded property table)
- **Derived findings:** {e.g. pre-modelled fracture rather than runtime fracture;
  MatCap-based shading; built-in-primitive objects; runtime-generated geometry}
- **Not recovered:** MonoBehaviour/ScriptableObject field values (balance tables,
  tuning configs), shader HLSL, IL2CPP method bodies — plus anything listed in
  `coverage-report.md`. State this plainly; do not imply full coverage.
- **Legal:** extracted art is reference material. The transferable output is the
  structure — level schema, physics constants, entity taxonomy, architecture.

## 5. Effort Estimate (AI-Assisted)
{effort table from effort-estimation-guide}
**Total: {min}–{max} AI Sprints** (1 sprint ≈ one focused Claude Code session).
Uncertainty band: {±%} due to {reason}.

## 6. Infrastructure Cost Estimate (monthly)
{MVP/Growth/Scale table from infra-cost-guide}
Biggest cost driver: {item}.

## 7. Market Analysis
- Current app metrics: installs {x}, rating {y}, review velocity {if known}.
- Competitor landscape: {2-4 named competitors}.
- Target market size: {rough estimate + basis}.
- Differentiation opportunities: {list}.

## 8. Viability Verdict
**{GO / CONDITIONAL GO / NO GO}**
- Key risks: {list}
- Key opportunities: {list}
- Recommendation rationale: {2-3 sentences tying effort+cost vs market}.

## 9. Next Step
{Link to implementation plan if user proceeds, else "report only".}
