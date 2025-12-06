#!/usr/bin/env python3
"""
Write a synthetic BrowserStack payload into the latest (or specified) run folder.
- Works on Streamlit Cloud and locally.
- Resolves the run directory robustly (CLI arg, runs/latest symlink, newest run_*).
- Accepts optional CLI args: [status] [run_dir]
    status: passed | failed | errored (default: passed)
    run_dir: path to a specific synthetic_demo/runs/run_*
"""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]   # .../synthetic_demo
RUNS = ROOT / "runs"


def latest_run_dir(arg_path: str | None = None) -> Path:
    """Return the run directory to write into."""
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
    # CLI: [status] [run_dir]
    status = "passed"
    run_arg = None
    if len(sys.argv) >= 2 and sys.argv[1]:
        status = sys.argv[1].strip()
    if len(sys.argv) >= 3 and sys.argv[2]:
        run_arg = sys.argv[2].strip()

    rd = latest_run_dir(run_arg)

    payload = {
        "build_id": f"bs-{int(time.time())}",
        "device": "Google Pixel 7 Pro",
        "os": "Android 14",
        "suite": "Synthetic::ModifyRoom",
        "status": status,
        "video_url": "https://browserstack.example/video.mp4",
        "logs_url": "https://browserstack.example/logs.txt"
    }

    out = rd / "browserstack_run.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"BrowserStack synthetic: {out}")


if __name__ == "__main__":
    main()
