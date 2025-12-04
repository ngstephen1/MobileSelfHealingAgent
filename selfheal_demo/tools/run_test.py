#!/usr/bin/env python3
import json, os, time, shutil, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
DATA = os.path.join(ROOT, "data")
REPORTS = os.path.join(ROOT, "reports")

os.makedirs(REPORTS, exist_ok=True)

SELECTORS = os.path.join(ASSETS, "selectors.json")
SEMANTICS = os.path.join(DATA, "semantics_before.txt")
UIAUTO = os.path.join(DATA, "uiauto_before.xml")
FAILING_KEY = "btn.viewRates"  # logical key our tests expect

def load_selectors():
    with open(SELECTORS, "r") as f:
        return json.load(f)

def semantics_has_testtag(path, tag):
    if not os.path.exists(path): return False
    return re.search(r"TestTag\s*=\s*'{}'".format(re.escape(tag)),
                     open(path, encoding="utf-8", errors="ignore").read()) is not None

def semantics_has_text(path, text):
    if not os.path.exists(path): return False
    return text.lower() in open(path, encoding="utf-8", errors="ignore").read().lower()

def simulate_test():
    sel = load_selectors()
    spec = sel.get(FAILING_KEY, {})
    test_tag = spec.get("testTag")
    text = spec.get("text")
    if test_tag and semantics_has_testtag(SEMANTICS, test_tag):
        return True, f"Found TestTag={test_tag}"
    if text and semantics_has_text(SEMANTICS, text):
        return True, f"Found Text={text}"
    return False, f"Selector not found (key={FAILING_KEY}, testTag={test_tag}, text={text})"

def write_failure_bundle(msg):
    run_id = time.strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(REPORTS, f"run_{run_id}")
    os.makedirs(out_dir, exist_ok=True)
    shutil.copy(SEMANTICS, os.path.join(out_dir, "semantics.txt"))
    shutil.copy(UIAUTO, os.path.join(out_dir, "uiauto.xml"))
    open(os.path.join(out_dir, "screenshot.txt"), "w").write("<<placeholder screenshot>>")
    bundle = {
      "test": "DemoTest::test_view_rates_button",
      "failing_label": FAILING_KEY,
      "message": msg,
      "artifacts": {
        "semantics": os.path.join(out_dir, "semantics.txt"),
        "uiauto": os.path.join(out_dir, "uiauto.xml"),
        "screenshot": os.path.join(out_dir, "screenshot.txt")
      }
    }
    with open(os.path.join(out_dir, "bundle.json"), "w") as f:
        json.dump(bundle, f, indent=2)
    return out_dir

if __name__ == "__main__":
    print("== Running demo test ==")
    ok, info = simulate_test()
    if ok:
        print(f"[PASS] {info}")
    else:
        print(f"[FAIL] {info}")
        out = write_failure_bundle(info)
        print(f"[BUNDLE] Failure bundle written to: {out}")
        print("Next: run `python3 tools/heal.py` to self-heal and then re-run this test.")