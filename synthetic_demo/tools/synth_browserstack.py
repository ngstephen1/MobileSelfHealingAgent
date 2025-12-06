#!/usr/bin/env python3
import os, json, glob, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / "runs"
def main(status="passed"):
    runs = sorted(glob.glob(str(OUTDIR / "run_*")), key=os.path.getmtime)
    if not runs: raise SystemExit("No runs. Simulate first.")
    r = Path(runs[-1])
    data = {
      "build_id": f"bs-{int(time.time())}",
      "device": "Google Pixel 7 Pro",
      "os": "Android 14",
      "suite": "Synthetic::ModifyRoom",
      "status": status,
      "video_url": "https://browserstack.example/video.mp4",
      "logs_url": "https://browserstack.example/logs.txt"
    }
    (r / "browserstack_run.json").write_text(json.dumps(data, indent=2))
    print("BrowserStack synthetic:", r / "browserstack_run.json")
if __name__ == "__main__":
    main("passed")
