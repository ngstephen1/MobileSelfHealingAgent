#!/usr/bin/env python3
import json, os, math

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, "config", "home_rois.json")
SEL = os.path.join(ROOT, "outputs", "selectors.json")

def center(box): x,y,w,h = box; return (x + w/2.0, y + h/2.0)

def propose_for_key(failing_key):
    cfg = json.load(open(CFG))
    sels = json.load(open(SEL))
    # If we already have a selector mapping, return it
    if failing_key in sels:
        return sels[failing_key]["testTag"], 0.99, "existing mapping"
    # Otherwise, find nearest ROI center to an expected anchor
    # Demo heuristic: map unknown 'tab.*' to nearest known tab by x-position
    tabs = [r for r in cfg["rois"] if r["key"].startswith("tab.")]
    if not tabs: return None, 0.0, "no tabs found"
    # Fallback: choose by lexicographic proximity if names similar
    best = sorted(tabs, key=lambda r: abs(len(r["key"]) - len(failing_key)))[0]
    candidate_key = best["key"]
    testTag = f'home.{candidate_key}'
    return testTag, 0.65, f"nearest-ROI heuristic from {candidate_key}"

def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: visual_heal.py <failing_key>")
        return
    failing = sys.argv[1]
    tag, conf, why = propose_for_key(failing)
    if not tag:
        print("No proposal.")
    else:
        print(f"Proposal for {failing}: testTag={tag} (confidence {conf:.2f}) — {why}")

if __name__ == "__main__":
    main()