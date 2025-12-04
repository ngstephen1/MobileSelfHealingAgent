#!/usr/bin/env python3
import os, json, re, glob
from math import exp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
REPORTS = os.path.join(ROOT, "reports")
SELECTORS = os.path.join(ASSETS, "selectors.json")

def parse_testtags(semantics_txt):
    txt = open(semantics_txt, encoding="utf-8", errors="ignore").read()
    return re.findall(r"TestTag\s*=\s*'([^']+)'", txt), txt

def levenshtein(a, b):
    a, b = a.lower(), b.lower()
    dp = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev = dp[0]; dp[0] = i
        for j, cb in enumerate(b, 1):
            cur = dp[j]
            dp[j] = min(dp[j] + 1, dp[j-1] + 1, prev + (0 if ca == cb else 1))
            prev = cur
    return dp[-1]

def confidence(tag, failing_key, txt):
    sim = 1 / (1 + levenshtein(tag, failing_key))
    in_context = 1.0 if "screen.searchResults" in txt else 0.7
    raw = 0.7 * sim + 0.3 * in_context
    # logistic squash 0..1
    return 1 / (1 + exp(-6 * (raw - 0.5)))

def update_selectors(failing_key, new_tag):
    sel = json.load(open(SELECTORS, "r")) if os.path.exists(SELECTORS) else {}
    sel[failing_key] = {"testTag": new_tag}
    json.dump(sel, open(SELECTORS, "w"), indent=2)

def write_report(folder, failing_key, new_tag, conf):
    path = os.path.join(folder, "heal_report.md")
    with open(path, "w") as f:
        f.write("# Self-Heal Patch\n\n")
        f.write(f"- Failing key: `{failing_key}`\n")
        f.write(f"- Proposed testTag: `{new_tag}` (confidence {conf:.2f})\n")
        f.write("- Reason: Prefer stable testTag; ranked by similarity and ancestor context.\n")
        f.write("- Updated file: `selfheal_demo/assets/selectors.json`\n")
    return path

if __name__ == "__main__":
    bundles = sorted(glob.glob(os.path.join(REPORTS, "run_*", "bundle.json")), key=os.path.getmtime)
    if not bundles:
        raise SystemExit("No failure bundles found. Run the test first.")
    bundle_path = bundles[-1]
    bundle = json.load(open(bundle_path, "r"))
    failing_key = bundle.get("failing_label", "unknown")
    semantics = bundle["artifacts"]["semantics"]

    cands, txt = parse_testtags(semantics)
    if not cands:
        raise SystemExit("No candidate TestTag found; manual review required.")
    # pick closest to failing key
    best = sorted(cands, key=lambda t: levenshtein(t, failing_key))[0]
    conf = confidence(best, failing_key, txt)

    update_selectors(failing_key, best)
    report = write_report(os.path.dirname(bundle_path), failing_key, best, conf)

    print("== Healer ==")
    print(f"- Bundle: {bundle_path}")
    print(f"- Failing key: {failing_key}")
    print(f"- Proposed testTag: {best} (confidence {conf:.2f})")
    print(f"- selectors.json updated")
    print(f"- Report: {report}")
    print("Re-run: `python3 tools/run_test.py` (should PASS now).")