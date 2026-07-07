#!/usr/bin/env python3
"""Turn a coverage manifest into an honest covered/partial/missing report.

Manifest shape:
  {"engine": str,
   "assets": {"expected": int, "extracted": int, "by_type": {type: int}},
   "mechanics": [{"name": str, "confidence": str}],
   "notes": [str]}
Stdlib only.
"""
import argparse, json, sys


def rollup(expected, extracted):
    if extracted >= expected and expected > 0:
        return "COVERED"
    if extracted == 0:
        return "MISSING"
    return "PARTIAL"


def render(m):
    a = m.get("assets", {}) or {}
    exp, ext = int(a.get("expected", 0)), int(a.get("extracted", 0))
    status = rollup(exp, ext)
    unaccounted = max(exp - ext, 0)
    lines = []
    lines.append(f"# Coverage Report — {m.get('engine', 'unknown')}")
    lines.append("")
    lines.append("> Extracted assets are **reference only** — recreate in the same style, not 1:1.")
    lines.append("")
    lines.append("## Assets")
    lines.append(f"- Status: **{status.lower()}** ({ext}/{exp} entries extracted)")
    if unaccounted:
        lines.append(f"- Not extracted: **{unaccounted}** (unsupported format / encrypted / see notes)")
    by_type = a.get("by_type", {}) or {}
    if by_type:
        lines.append("")
        lines.append("| Type | Extracted |")
        lines.append("|---|---|")
        for t in sorted(by_type):
            lines.append(f"| {t} | {by_type[t]} |")
    lines.append("")
    lines.append("## Mechanics (by confidence)")
    buckets = {}
    for item in m.get("mechanics", []) or []:
        buckets.setdefault(item.get("confidence", "unknown"), []).append(item.get("name", "?"))
    if not buckets:
        lines.append("- none recovered")
    for conf in ("observed", "inferred", "signature-only", "not-recoverable", "unknown"):
        if conf in buckets:
            lines.append(f"- **{conf}**: " + ", ".join(sorted(buckets[conf])))
    notes = m.get("notes", []) or []
    if notes:
        lines.append("")
        lines.append("## Notes / why incomplete")
        for n in notes:
            lines.append(f"- {n}")
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    ap.add_argument("--out")
    args = ap.parse_args()
    with open(args.manifest) as f:
        m = json.load(f)
    report = render(m)
    if args.out:
        with open(args.out, "w") as f:
            f.write(report)
    else:
        sys.stdout.write(report)


if __name__ == "__main__":
    main()
