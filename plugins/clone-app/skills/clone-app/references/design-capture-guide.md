# Design Capture Guide

Goal: recover enough of the target's visual design to clone it **pixel-perfect**.
Two sources, always combined:

1. **APK resources** (`extract-design.py` on the decompile root) →
   `design-tokens.json` + `design-digest.md`. Real colors, dimens, theme,
   fonts, layout inventory, launcher icon.
2. **Play Store screenshots** (`scrape-play-store.py` → `screenshot_urls`,
   downloaded to `$WORK/extracted/store/screenshots/`). The visual ground truth for layout,
   composition, and anything not in res.

## Framework-aware reading (confidence)

| Framework | What's in Android res | Confidence | Fallback |
|---|---|---|---|
| Native (XML views) | colors, dimens, themes, **layouts** | high | — |
| Jetpack Compose | colors/dimens often in res; **no layouts** (UI in Kotlin) | med | grep sources for `Color(0x…)`, `.dp`, `.sp`; screenshots |
| Flutter | almost nothing (Dart owns design) | low | screenshots primary; note low confidence |
| React Native | almost nothing (JS owns styles) | low | screenshots primary |
| Unity | n/a — use `unity-re-guide.md` | low | game assets + screenshots |

`extract-design.py` stamps each token group with `confidence`. When `med`/`low`,
the build spec relies more on screenshots and says so.

## What to record in `design-tokens.json`

Top-level scalar fields always present: `package` (caller-supplied), `source`
(always `"apk-resources"`), `framework` (detected framework string).
Token groups — each an object with `values` and `confidence`: `colors` ·
`dimens` (spacing + `sp` text sizes) · `typography` (font files, text sizes) ·
`shapes` (corner/radius dimens) · `theme` (name, parent, dark flag, items) ·
`icon` (launcher icon path) · `layouts` (count + file names).

## Turning tokens into a spec

Map each token group into the build spec's "Design system" section: palette
(named colors → roles), type scale (text sizes + fonts), spacing scale (dimens),
corner radii, light/dark. Pair every screen in the spec with its closest
`screenshots/NN.png`.
