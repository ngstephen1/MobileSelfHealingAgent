#!/usr/bin/env python3
import os, json, glob
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / "runs"
def main(testKey="MBL-TEST-4242"):
    runs = sorted(glob.glob(str(OUTDIR / "run_*")), key=os.path.getmtime)
    if not runs: raise SystemExit("No runs. Simulate first.")
    r = Path(runs[-1])
    bs = json.loads((r / "browserstack_run.json").read_text()) if (r / "browserstack_run.json").exists() else {}
    heal = (r / "heal_report.md").read_text() if (r / "heal_report.md").exists() else ""
    payload = {
      "testKey": testKey,
      "status": bs.get("status","failed"),
      "evidence": {
        "browserstack": bs,
        "healReport": heal
      },
      "comment": "Synthetic update: linked BrowserStack run & self-heal report."
    }
    (r / "qmetry_update.json").write_text(json.dumps(payload, indent=2))
    print("QMetry synthetic:", r / "qmetry_update.json")
if __name__ == "__main__":
    main()
