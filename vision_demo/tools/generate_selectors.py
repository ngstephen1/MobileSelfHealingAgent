#!/usr/bin/env python3
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, "config", "home_rois.json")
OUT = os.path.join(ROOT, "outputs", "selectors.json")

def to_test_tag(prefix, key):
    # home.search.bar -> home.search.bar ; tab.* preserved
    return f"{prefix}{key}" if not key.startswith("tab.") else f"{prefix}{key}"

def main():
    cfg = json.load(open(CFG, "r"))
    prefix = cfg.get("testTagConvention", {}).get("prefix", "")
    out = {}
    for r in cfg["rois"]:
        key = r["key"]
        if key == "screen.home":  # screen tag
            out[key] = {"testTag": "screen.home"}
            continue
        ttag = to_test_tag(prefix, key)
        out[key] = {
            "testTag": ttag,
            "labelHint": r.get("label", ""),
            "type": r.get("type", "control")
        }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=2)
    print(f"Selector proposals saved to: {OUT}")

if __name__ == "__main__":
    main()