#!/usr/bin/env python3
"""
Collects per-run healing metrics into runs/history.csv.
- Works with new run-relative artifact layout.
- Tolerates old absolute paths in bundle.json.
- Extracts chosen strategy (semantic/visual/...) and confidence from heal_report.md.
- Falls back cleanly if a heal hasn't been performed yet.
"""

import csv, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]        # .../synthetic_demo
RUNS = ROOT / "runs"
HIST = RUNS / "history.csv"


def read_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def parse_heal_report(p: Path):
    """Return (chosen_key, confidence, android_tag, ios_id) from heal_report.md.
    Expected line (from heal.py):
      - Proposed: `testTag=btn.viewPrices` (source=semantic, confidence=0.93)
    """
    chosen_key = ""
    confidence = ""
    android_tag = ""
    ios_id = ""

    if not p.exists():
        return chosen_key, confidence, android_tag, ios_id

    txt = p.read_text(encoding="utf-8", errors="ignore")

    # Extract proposed testTag (android)
    m_tag = re.search(r"Proposed:\s*`testTag=([A-Za-z0-9._\-]+)`", txt)
    if m_tag:
        android_tag = m_tag.group(1)
        ios_id = android_tag  # synthetic demo mirrors id across platforms

    # Extract source and confidence
    m_src = re.search(r"source\s*=\s*([A-Za-z0-9_\-]+)", txt)
    if m_src:
        chosen_key = m_src.group(1)
    m_conf = re.search(r"confidence\s*=\s*([0-9]*\.?[0-9]+)", txt)
    if m_conf:
        confidence = m_conf.group(1)

    return chosen_key, confidence, android_tag, ios_id


def main():
    rows = []
    runs = sorted([p for p in RUNS.glob("run_*") if p.is_dir()])
    for run_dir in runs:
        bundle = read_json(run_dir / "bundle.json")
        failing_key = bundle.get("failing_label") or bundle.get("failing_key") or ""

        chosen_key, confidence, android_tag, ios_id = parse_heal_report(run_dir / "heal_report.md")

        rows.append({
            "run": run_dir.name,
            "failing_key": failing_key,
            "chosen_key": chosen_key,
            "confidence": confidence,
            "android_tag": android_tag,
            "ios_id": ios_id,
        })

    # Write CSV with stable header
    HIST.parent.mkdir(parents=True, exist_ok=True)
    fields = ["run", "failing_key", "chosen_key", "confidence", "android_tag", "ios_id"]
    with HIST.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"Wrote {HIST} with {len(rows)} rows")


if __name__ == "__main__":
    main()