#!/usr/bin/env python3
import os, json, glob, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repo root
DEMO = ROOT / "selfheal_demo" / "reports"
OUT  = ROOT / "tmp" / "selfheal" / "demo_run"

def main():
    runs = sorted(glob.glob(str(DEMO / "run_*")), key=os.path.getmtime)
    if not runs:
        raise SystemExit("No demo runs found. Run selfheal_demo/tools/run_test.py first.")
    src = Path(runs[-1])
    semantics = src / "semantics.txt"
    uiauto    = src / "uiauto.xml"
    shot      = src / "screenshot.txt"

    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copy(semantics, OUT / "semantics.txt")
    shutil.copy(uiauto,    OUT / "uiauto.xml")
    shutil.copy(shot,      OUT / "screenshot.txt")

    bundle = {
      "test": "DemoTest::test_view_rates_button",
      "failing_label": "btn.viewRates",
      "message": "Selector not found",
      "artifacts": {
        "semantics": str(OUT / "semantics.txt"),
        "uiauto":    str(OUT / "uiauto.xml"),
        "screenshot":str(OUT / "screenshot.txt")
      }
    }
    with open(OUT / "bundle.json", "w") as f:
        json.dump(bundle, f, indent=2)

    print(f"Shimmed bundle → {OUT / 'bundle.json'}")

if __name__ == "__main__":
    main()