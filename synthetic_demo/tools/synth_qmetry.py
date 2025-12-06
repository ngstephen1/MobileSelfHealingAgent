#!/usr/bin/env python3
"""
Write a synthetic QMetry payload into the latest (or specified) run folder.

Usage:
  python synthetic_demo/tools/synth_qmetry.py [testKey] [status] [run_dir]

Args:
  testKey   (optional): QMetry test key (default: MBL-TEST-4242)
  status    (optional): passed | failed | blocked | notrun (default: derived from BrowserStack or 'passed')
  run_dir   (optional): path to a specific synthetic_demo/runs/run_*

Behavior:
- Resolves the run directory robustly: CLI arg → runs/latest symlink → newest run_*.
- Pulls BrowserStack payload (if present) and the heal report for evidence.
- Writes qmetry_update.json with UTF-8, pretty-printed.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # .../synthetic_demo
RUNS = ROOT / "runs"


def latest_run_dir(arg_path: str | None = None) -> Path:
    """Return the target run directory."""
    # 1) explicit arg
    if arg_path:
        p = Path(arg_path).expanduser()
        if p.is_dir():
            return p

    # 2) runs/latest symlink
    lat = RUNS / "latest"
    if lat.exists():
        try:
            return lat.resolve()
        except Exception:
            pass

    # 3) newest run_*
    runs = sorted([p for p in RUNS.glob("run_*") if p.is_dir()])
    if not runs:
        raise SystemExit("No runs. Simulate first.")
    return runs[-1]


def main():
    # Parse CLI args
    test_key = "MBL-TEST-4242"
    status_override = None
    run_arg = None

    if len(sys.argv) >= 2 and sys.argv[1]:
        test_key = sys.argv[1].strip()
    if len(sys.argv) >= 3 and sys.argv[2]:
        status_override = sys.argv[2].strip()
    if len(sys.argv) >= 4 and sys.argv[3]:
        run_arg = sys.argv[3].strip()

    rd = latest_run_dir(run_arg)

    # Load BrowserStack payload and heal report if present
    bs_path = rd / "browserstack_run.json"
    qm_status = "passed"
    bs_payload = {}
    if bs_path.exists():
        try:
            bs_payload = json.loads(bs_path.read_text(encoding="utf-8"))
            qm_status = bs_payload.get("status") or qm_status
        except Exception:
            bs_payload = {}

    if status_override:
        qm_status = status_override

    heal_path = rd / "heal_report.md"
    heal_txt = ""
    if heal_path.exists():
        try:
            heal_txt = heal_path.read_text(encoding="utf-8")
        except Exception:
            heal_txt = ""

    payload = {
        "testKey": test_key,
        "status": qm_status,
        "evidence": {
            "browserstack": bs_payload,
            "healReport": heal_txt
        },
        "comment": "Synthetic update: linked BrowserStack run & self-heal report."
    }

    out = rd / "qmetry_update.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"QMetry synthetic: {out}")


if __name__ == "__main__":
    main()
