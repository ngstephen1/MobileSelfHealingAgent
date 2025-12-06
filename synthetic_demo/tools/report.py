#!/usr/bin/env python3
import os, glob, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
runs = sorted(glob.glob(str(ROOT / "runs" / "run_*")), key=os.path.getmtime)
if not runs: raise SystemExit("No runs found.")
r = Path(runs[-1])
bundle = json.loads((r / "bundle.json").read_text()) if (r / "bundle.json").exists() else {}
bs = json.loads((r / "browserstack_run.json").read_text()) if (r / "browserstack_run.json").exists() else {}
heal = (r / "heal_report.md").read_text() if (r / "heal_report.md").exists() else "(no heal)"
print("=== Synthetic QE Report ===")
print("Run folder:", r)
print("\n-- Failure Bundle --")
print(json.dumps(bundle, indent=2))
print("\n-- Heal Report --")
print(heal.strip())
print("\n-- BrowserStack --")
print(json.dumps(bs, indent=2))
print("\n-- QMetry --")
q = (r / "qmetry_update.json")
print(q.read_text() if q.exists() else "(no qmetry payload)")
