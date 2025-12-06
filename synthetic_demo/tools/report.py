#!/usr/bin/env python3
# Robust report: handles run-relative artifacts and old absolute paths, and lets you pass a run dir.
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]   # .../synthetic_demo
RUNS = ROOT / "runs"


def latest_run_dir() -> Path:
    """
    Resolve the run directory to report on.
    Preference:
      1) CLI arg (explicit path to a run dir)
      2) runs/latest symlink (if present)
      3) newest runs/run_* directory
    """
    # 1) CLI arg
    if len(sys.argv) > 1:
        d = Path(sys.argv[1]).expanduser()
        if d.is_dir():
            return d

    # 2) 'latest' symlink
    lat = RUNS / "latest"
    if lat.exists():
        try:
            return lat.resolve()
        except Exception:
            pass

    # 3) newest run_*
    runs = sorted([p for p in RUNS.glob("run_*") if p.is_dir()])
    if not runs:
        raise SystemExit("No runs found.")
    return runs[-1]


def pick_artifact(run_dir: Path, val: str | None, default_name: str) -> Path:
    """
    Resolve an artifact robustly:
      - Prefer <run_dir>/<basename(val)>
      - Then <run_dir>/<val> if val was relative
      - Then <val> (absolute) if it exists
      - Finally <run_dir>/<default_name>
    """
    candidates = []
    if val:
        p = Path(val)
        candidates += [run_dir / p.name, run_dir / val, p]
    candidates.append(run_dir / default_name)
    for c in candidates:
        try:
            if c.exists():
                return c
        except Exception:
            pass
    return run_dir / default_name


def read_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_text(p: Path, default: str = "") -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return default


if __name__ == "__main__":
    rd = latest_run_dir()

    # Load bundle and resolve artifacts (works even if old bundle had absolute paths)
    bundle_path = rd / "bundle.json"
    bundle = read_json(bundle_path)
    art = bundle.get("artifacts", {}) or {}
    sem = pick_artifact(rd, art.get("semantics"),  "semantics.txt")
    uia = pick_artifact(rd, art.get("uiauto"),     "uiauto.xml")
    scr = pick_artifact(rd, art.get("screenshot"), "screenshot.txt")

    # Heal, BrowserStack, QMetry
    heal_report = read_text(rd / "heal_report.md", "(no heal)")
    bs_payload  = read_json(rd / "browserstack_run.json")
    qm_payload  = read_text(rd / "qmetry_update.json", "")

    # Print consolidated report
    print("=== Synthetic QE Report ===")
    print("Run folder:", rd)

    print("\n-- Failure Bundle --")
    print(json.dumps(bundle, indent=2, ensure_ascii=False) if bundle else "(no bundle)")

    print("\n-- Heal Report --")
    print(heal_report.strip() if heal_report else "(no heal)")

    print("\n-- BrowserStack --")
    print(json.dumps(bs_payload, indent=2, ensure_ascii=False) if bs_payload else "(no browserstack payload)")

    print("\n-- QMetry --")
    print(qm_payload if qm_payload else "(no qmetry payload)")

    # Helpful debug: show resolved artifact locations
    print("\n-- Artifacts (resolved) --")
    print(json.dumps({
        "semantics": str(sem),
        "uiauto": str(uia),
        "screenshot": str(scr)
    }, indent=2))
