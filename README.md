# App Clone Pipeline — discover → analyze → build (Claude Code plugins)

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0) [![GitHub stars](https://img.shields.io/github/stars/masa2146/clone-app-skill?style=social)](https://github.com/masa2146/clone-app-skill/stargazers) [![GitHub last commit](https://img.shields.io/github/last-commit/masa2146/clone-app-skill)](https://github.com/masa2146/clone-app-skill/commits/master)

A Claude Code **plugin marketplace** that turns "what should I build?" into a working clone. It chains four plugins into a **discover → analyze → build** pipeline: scan the market for opportunities, reverse-engineer a target app, estimate the effort and infrastructure to clone it, then build a verified, prod-ready clone — apps *and* games.

The pipeline runs as **skill handoffs, not a central orchestrator**: each plugin is independently installable and hands its output to the next.

> **Origin:** This project began as a fork of Simone Avogadro's [android-reverse-engineering-skill](https://github.com/SimoneAvogadro/android-reverse-engineering-skill) and grew a clone/build pipeline on top. That reverse-engineering skill lives on here as one of the four plugins, vendored byte-identical so it can still track upstream. See [Origin & attribution](#origin--attribution).

## Table of Contents

- [The pipeline](#the-pipeline)
- [The four plugins](#the-four-plugins)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Repository structure](#repository-structure)
- [Origin & attribution](#origin--attribution)
- [Disclaimer](#disclaimer)
- [License](#license)

## The pipeline

```text
  market-research        clone-app                         clone-build
 ┌──────────────┐   ┌──────────────────────┐         ┌──────────────────────┐
 │ scan market, │   │ RE the app (drives   │         │ build a verified,    │
 │ score & rank │──▶│ android-reverse-     │────────▶│ prod-ready clone via │
 │ candidates   │   │ engineering) → effort│  build- │ a gated task graph   │
 │ (non-repeat) │   │ + cost + viability + │  spec   │ (app or game branch) │
 └──────────────┘   │ clone-build-spec.md  │         └──────────────────────┘
     discover       └──────────────────────┘              build
                          analyze
```

Each stage is optional and standalone — start anywhere. `clone-app` can drive the reverse-engineering plugin directly from a Google Play URL; `market-research` feeds it candidates; `clone-build` consumes the spec `clone-app` produces. Effort throughout is measured in **AI Sprints** (one focused Claude session), never calendar time.

## The four plugins

| Plugin | Stage | What it does |
|--------|-------|--------------|
| **market-research** | discover | Autonomously scans the app/game market (free web search + Apple App Store chart feeds + LLM trend synthesis), scores ≥10 non-repeating clone candidates by cloneability + market opportunity + monetization fit, and hands picks to `clone-app`. |
| **clone-app** | analyze | Takes a Google Play URL, drives reverse engineering, scrapes store metrics, estimates AI-assisted clone effort + infrastructure cost, judges market viability, and assembles a standalone `clone-build-spec.md`. Detects the game engine (Unity / Unreal / Godot / native) and dispatches per-engine extraction of mechanics + assets. |
| **clone-build** | build | Builds a verified, prod-ready clone (app *or* game) from `clone-build-spec.md`, driving a deterministic task graph where every task carries a machine-checkable gate (build / TDD / visual-diff / launch-crash). |
| **android-reverse-engineering** | engine | Decompiles APK/XAPK/JAR/AAR with jadx and Fernflower/Vineflower, recovers R8-obfuscated Kotlin names, and extracts HTTP APIs (Retrofit/OkHttp/Ktor/Apollo/Koin). Vendored byte-identical from upstream; `clone-app` calls it as its RE engine. |

## Installation

Inside Claude Code, add this marketplace and install the plugins you want:

```text
/plugin marketplace add masa2146/clone-app-skill
/plugin install market-research@clone-app-skill
/plugin install clone-app@clone-app-skill
/plugin install clone-build@clone-app-skill
/plugin install android-reverse-engineering@clone-app-skill
```

Or from a local clone:

```bash
git clone https://github.com/masa2146/clone-app-skill.git
```

```text
/plugin marketplace add /path/to/clone-app-skill
```

The reverse-engineering plugin needs Java JDK 17+ and [jadx](https://github.com/skylot/jadx) (plus optional [Vineflower](https://github.com/Vineflower/vineflower) / [dex2jar](https://github.com/ThexXTURBOXx/dex2jar)); game-asset extraction uses an opt-in Python venv. See each plugin's own README and reference guides for details.

## Quick start

```text
# Discover: what should I build?
/market-research

# Analyze: is this specific app worth cloning, and how much work is it?
/clone-app https://play.google.com/store/apps/details?id=com.example.app

# Build: turn the produced spec into a verified clone
/clone-build

# Or just reverse-engineer an APK you already have
/decompile path/to/app.apk
```

Each skill also activates from natural language — e.g. "research trending games to clone", "analyze cloning this app", "reverse engineer this APK".

## Repository structure

```text
clone-app-skill/
├── .claude-plugin/
│   └── marketplace.json          # Catalog listing all four plugins
├── plugins/
│   ├── android-reverse-engineering/   # Vendored byte-identical from upstream — do not modify
│   ├── clone-app/                     # discover→analyze: RE, effort/cost, viability, build-spec
│   ├── market-research/               # discover: market scan → scored candidates
│   └── clone-build/                   # build: gated task graph → prod-ready clone
├── docs/superpowers/                  # Design specs + implementation plans behind each plugin
├── LICENSE
└── README.md
```

Each project plugin mirrors the same layout — `skills/<name>/{SKILL.md,scripts/,references/}`, `commands/<name>.md`, `tests/`, `.claude-plugin/plugin.json`, `README.md`.

## Origin & attribution

This repository is derived from **[SimoneAvogadro/android-reverse-engineering-skill](https://github.com/SimoneAvogadro/android-reverse-engineering-skill)** by [Simone Avogadro](https://github.com/SimoneAvogadro), licensed Apache-2.0. The `plugins/android-reverse-engineering/` tree is **kept byte-identical to upstream** so it can be resynced conflict-free (`git pull upstream master`); it retains its own README and full attribution. The `clone-app`, `market-research`, and `clone-build` plugins are new work added by this project on top of that foundation.

Thanks to the upstream contributors who shaped the reverse-engineering skill this project builds on:

- [@tajchert](https://github.com/tajchert) — Phase 0 fingerprinting, R8-resistant Kotlin name recovery, and Ktor / Apollo / Koin / HMAC extraction patterns
- [@philjn](https://github.com/philjn) — Native Windows / PowerShell support and split/bundled APK detection
- [@txhno](https://github.com/txhno) — Migration to the maintained [`ThexXTURBOXx/dex2jar`](https://github.com/ThexXTURBOXx/dex2jar) fork
- [@muqiao215](https://github.com/muqiao215) — Decompile partial-success handling, Fernflower timeout safeguard, intermediate-artifact directory
- [@kevinaimonster](https://github.com/kevinaimonster) — Chinese localization

## Disclaimer

These plugins are provided strictly for **lawful purposes**, including but not limited to:

- Security research and authorized penetration testing
- Interoperability analysis permitted under applicable law (e.g., EU Directive 2009/24/EC, US DMCA §1201(f))
- Malware analysis and incident response
- Market research, competitive analysis, and educational use

Reverse engineering, and building a clone of, software you do not own or lack permission to analyze may violate intellectual property laws, copyright, and computer-fraud statutes in your jurisdiction. **Extracted assets (art, audio, models) are copyrighted** — this pipeline treats them as *reference only* to be recreated in-style for authorized use, never as a byte-identical copy to ship. **You are solely responsible** for ensuring your use complies with all applicable laws, regulations, and terms of service. The authors disclaim any liability for misuse.

## License

Apache 2.0 — see [LICENSE](LICENSE)
