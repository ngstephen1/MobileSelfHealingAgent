#!/usr/bin/env python3
import subprocess, sys, pathlib, json

ROOT = pathlib.Path(__file__).resolve().parents[1]
tools = ROOT / "tools"

def run(*args):
    print(f"\n$ {' '.join(args)}")
    res = subprocess.run(args, cwd=tools, text=True)
    if res.returncode != 0:
        sys.exit(res.returncode)

def last_status():
    cat = json.load(open(ROOT / "config" / "selector_catalog.json"))
    return "passed" if cat.get("btn.viewRates", {}).get("testTag") == "btn.viewPrices" else "failed"

if __name__ == "__main__":
    # 1) generate feature
    run("python3", str(tools / "generate_feature.py"))
    # 2) first run -> FAIL (creates bundle)
    run("python3", str(tools / "simulate_run.py"))
    # 3) heal (semantics first, vision fallback)
    run("python3", str(tools / "heal.py"))
    # 4) re-run -> PASS
    run("python3", str(tools / "simulate_run.py"))
    # 5) synthetic BrowserStack/QMetry aligned to run status
    status = last_status()
    run("python3", str(tools / "synth_browserstack.py"))
    run("python3", str(tools / "synth_qmetry.py"))
    # 6) consolidated report
    run("python3", str(tools / "report.py"))
    print("\nDone ✅  (synthetic_demo/runs/<latest> has bundle, heal_report.md, BS/QMetry json)")