#!/usr/bin/env python3
"""
Collect per-run healing metrics into runs/history.csv.

Behavior:
- Scans synthetic_demo/runs/run_* (works locally and on Streamlit Cloud).
- Prefers structured metrics from heal_result.json (if present).
- Falls back to parsing heal_report.md for older runs.
- Writes a stable CSV with columns:
    run, failing_key, chosen_key, confidence, android_tag, ios_id, ts
"""

import csv
import json
import re
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
    """Fallback for older runs without heal_result.json.
    Returns (chosen_key, confidence, android_tag, ios_id).
    Expected line in markdown:
        - Proposed: `testTag=btn.viewPrices` (source=semantic, confidence=0.93)
    """
    chosen_key = ""
    confidence = ""
    android_tag = ""
    ios_id = ""

    if not p.exists():
        return chosen_key, confidence, android_tag, ios_id

    txt = p.read_text(encoding="utf-8", errors="ignore")

    m_tag = re.search(r"Proposed:\s*`testTag=([A-Za-z0-9._\-]+)`", txt)
    if m_tag:
        android_tag = m_tag.group(1)
        ios_id = android_tag  # synthetic demo mirrors Android

    m_src = re.search(r"source\s*=\s*([A-Za-z0-9_\-]+)", txt)
    if m_src:
        chosen_key = m_src.group(1)

    m_conf = re.search(r"confidence\s*=\s*([0-9]*\.?[0-9]+)", txt)
    if m_conf:
        confidence = m_conf.group(1)

    return chosen_key, confidence, android_tag, ios_id


def main():
    rows = []

    run_dirs = sorted([p for p in RUNS.glob("run_*") if p.is_dir()])
    if not run_dirs:
        print("No runs found. Generate one with simulate_run.py")

    for run_dir in run_dirs:
        bundle = read_json(run_dir / "bundle.json")
        failing_key = bundle.get("failing_label") or bundle.get("failing_key") or ""

        # Prefer structured JSON
        hrj = read_json(run_dir / "heal_result.json")
        if hrj:
            chosen_key  = hrj.get("chosen_key", "")
            confidence  = hrj.get("confidence", "")
            android_tag = (hrj.get("android") or {}).get("testTag", "")
            ios_id      = (hrj.get("ios") or {}).get("accessibilityId", "")
            ts_val      = hrj.get("ts", "")
        else:
            chosen_key, confidence, android_tag, ios_id = parse_heal_report(run_dir / "heal_report.md")
            ts_val = ""

        rows.append({
            "run": run_dir.name,
            "failing_key": failing_key,
            "chosen_key": chosen_key,
            "confidence": confidence,
            "android_tag": android_tag,
            "ios_id": ios_id,
            "ts": ts_val,
        })

    # Write CSV
    HIST.parent.mkdir(parents=True, exist_ok=True)
    fields = ["run", "failing_key", "chosen_key", "confidence", "android_tag", "ios_id", "ts"]
    with HIST.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"Wrote {HIST} with {len(rows)} rows")


if __name__ == "__main__":
    main()