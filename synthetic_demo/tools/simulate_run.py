#!/usr/bin/env python3
import os, re, json, time, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAT  = ROOT / "config" / "selector_catalog.json"
SEM  = ROOT / "data" / "semantics" / "screen_searchResults.txt"
UIA  = ROOT / "data" / "uiauto" / "screen_searchResults.xml"
RUNS = ROOT / "runs"
RUNS.mkdir(exist_ok=True, parents=True)

FAILING_KEY = "btn.viewRates"   # expected logical key

def semantics_has_testtag(tag):
    if not SEM.exists(): return False
    txt = SEM.read_text(encoding="utf-8", errors="ignore")
    return re.search(rf"TestTag\s*=\s*'{re.escape(tag)}'", txt) is not None

def run_once():
    sel = json.loads(CAT.read_text())
    cur = sel.get(FAILING_KEY, {})
    testTag = cur.get("testTag")
    if testTag and semantics_has_testtag(testTag):
        return True, f"Found {testTag}"
    return False, f"Missing tag in semantics for key={FAILING_KEY}, testTag={testTag}"

def write_bundle(msg):
    ts = time.strftime("%Y%m%d_%H%M%S")
    out = RUNS / f"run_{ts}"
    out.mkdir(parents=True, exist_ok=True)

    # Copy artifacts for this synthetic run
    shutil.copyfile(SEM, out / "semantics.txt")
    shutil.copyfile(UIA, out / "uiauto.xml")
    (out / "screenshot.txt").write_text("<<synthetic screenshot>>", encoding="utf-8")

    # IMPORTANT: keep artifact paths relative to the run folder so the demo
    # works both locally and in cloud containers.
    bundle = {
        "test": "Synthetic::ModifyRoom",
        "failing_label": FAILING_KEY,
        "message": msg,
        "run": out.name,  # convenience for dashboards
        "artifacts": {
            "semantics": "semantics.txt",
            "uiauto": "uiauto.xml",
            "screenshot": "screenshot.txt"
        }
    }

    (out / "bundle.json").write_text(json.dumps(bundle, indent=2), encoding="utf-8")

    # Maintain a helpful "latest" pointer (best-effort; ignore if fails)
    try:
        latest = RUNS / "latest"
        if latest.exists() or latest.is_symlink():
            latest.unlink()
        latest.symlink_to(out.name)
    except Exception:
        pass

    print("Bundle written:", out)
    return out

if __name__ == "__main__":
    ok, info = run_once()
    if ok:
        print("[PASS]", info)
    else:
        print("[FAIL]", info)
        write_bundle(info)
