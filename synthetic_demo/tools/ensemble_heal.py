#!/usr/bin/env python3
import json, re, glob, argparse
from pathlib import Path
try:
    from rapidfuzz.distance import Levenshtein as lev
    def lev_dist(a,b): return lev.distance(a,b)
except Exception:
    def lev_dist(a,b):
        # simple fallback
        dp = [[i+j if i*j==0 else 0 for j in range(len(b)+1)] for i in range(len(a)+1)]
        for i in range(1,len(a)+1):
            dp[i][0]=i
        for j in range(1,len(b)+1):
            dp[0][j]=j
        for i in range(1,len(a)+1):
            for j in range(1,len(b)+1):
                dp[i][j]=min(dp[i-1][j]+1, dp[i][j-1]+1, dp[i-1][j-1]+(a[i-1]!=b[j-1]))
        return dp[-1][-1]

ROOT = Path(__file__).resolve().parents[1]
CAT = ROOT / "config" / "selector_catalog.json"
PLAT = ROOT / "config" / "platform_map.json"
VISION_ROI = ROOT.parents[1] / "vision_demo" / "outputs" / "rois.json"  # optional if you produce it
ALIASES = {
  "btn.viewRates": ["btn.viewPrices", "btn.viewRate", "btn.pricesNow"],
  "btn.bookNow":   ["btn.reserve", "btn.reserveNow"],
  "tab.trips":     ["home.tab.trips", "tab.myTrips"]
}

def extract_candidates(sem_text: str, ios_json: str):
    cands = set()
    for m in re.finditer(r"TestTag='([^']+)'", sem_text):
        cands.add(m.group(1))
    try:
        ios = json.loads(ios_json)
        for e in ios.get("elements", []):
            if "accessibilityId" in e:
                cands.add(e["accessibilityId"])
    except Exception:
        pass
    return list(cands)

def roi_distance(tag: str):
    try:
        rois = json.loads(VISION_ROI.read_text())
        # distance from center to a canonical area; fallback 0.5
        r = rois.get(tag)
        if not r: return 0.5
        x,y,w,h = r["x"], r["y"], r["w"], r["h"]
        cx, cy = x+w/2, y+h/2
        return ((cx-0.5)**2 + (cy-0.5)**2)**0.5  # 0..~0.7
    except Exception:
        return 0.5

def score(failing_key, cand, sem_txt, ios_json):
    # text similarity + simple heuristics
    s_lev = 1/(1+lev_dist(failing_key, cand))
    click = 1.0 if "btn." in cand or "Button" in sem_txt else 0.5
    syn_bonus = 0.2 if (("rates" in failing_key and "prices" in cand) or ("prices" in failing_key and "rates" in cand)) else 0.0
    vis = 0.1 if "visible=true" in sem_txt else 0.0
    roi = 0.15*(1/(1+roi_distance(cand)))
    return s_lev + click + syn_bonus + vis + roi

def pick_ensemble(failing_key, sem_path: Path, ios_path: Path, gemini_suggest=None):
    sem_txt = sem_path.read_text()
    ios_json = ios_path.read_text() if ios_path.exists() else "{}"
    cands = set(extract_candidates(sem_txt, ios_json))
    cands.update(ALIASES.get(failing_key, []))
    if not cands:
        cands = {failing_key}
    scores = []
    for c in cands:
        s = score(failing_key, c, sem_txt, ios_json)
        if gemini_suggest and gemini_suggest.get("android",{}).get("testTag")==c:
            s += 0.3 * gemini_suggest.get("confidence", 0.6)  # trust but verify
        scores.append((c, s))
    scores.sort(key=lambda x: x[1], reverse=True)
    best, best_s = scores[0]
    return best, best_s, scores[:5]

def load_latest_or_specific(run_dir: Path|None):
    if run_dir:
        return run_dir
    runs = sorted([Path(p).parent for p in glob.glob(str(ROOT/"runs"/"run_*"/"bundle.json"))])
    return runs[-1] if runs else None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=str, help="path to a specific runs/run_xxx folder")
    ap.add_argument("--use-gemini", action="store_true", help="mix in Gemini 2.5 suggestion when available")
    args = ap.parse_args()

    run = load_latest_or_specific(Path(args.run) if args.run else None)
    if not run: raise SystemExit("No runs found.")
    bundle = json.loads((run/"bundle.json").read_text())
    failing = bundle["failing_label"]
    sem_path = Path(bundle["artifacts"]["semantics"])
    ios_path = run/"ios_tree.json"

    gem_suggest = None
    if args.use_gemini:
        try:
            from llm.gemini_client import multimodal_heal_gemini
            shot = ROOT.parents[1]/"vision_demo"/"outputs"/"bonvoy_annotated.png"
            gem_suggest = multimodal_heal_gemini(failing, sem_path.read_text(), ios_path.read_text() if ios_path.exists() else "{}", shot if shot.exists() else None)
        except Exception as e:
            print("[warn] gemini suggest failed:", e)

    best, score_v, top5 = pick_ensemble(failing, sem_path, ios_path, gemini_suggest=gem_suggest)

    # patch selector_catalog + platform_map
    cat = json.loads((CAT).read_text())
    cat[failing] = {"testTag": best}
    CAT.write_text(json.dumps(cat, indent=2))

    if PLAT.exists():
        pm = json.loads(PLAT.read_text())
        pm.setdefault(failing, {})
        pm[failing]["android"] = {"testTag": best}
        pm[failing]["ios"] = {"accessibilityId": best}
        PLAT.write_text(json.dumps(pm, indent=2))

    # write heal report
    hr = run/"heal_report.md"
    lines = [
      "# Self-Heal Patch (Ensemble)\n",
      f"- Failing key: `{failing}`\n",
      f"- Chosen: `{best}`  (score={score_v:.3f})\n",
      f"- Sources: {'Gemini+Semantic+Vision' if gem_suggest else 'Semantic+Vision'}\n",
    ]
    if gem_suggest:
        lines.append(f"- Gemini suggestion: android={gem_suggest['android']['testTag']} ios={gem_suggest['ios']['accessibilityId']} conf={gem_suggest['confidence']:.2f}\n")
        lines.append(f"- Rationale: {gem_suggest.get('rationale','')}\n")
    lines.append("\nTop candidates:\n")
    for cand, sc in top5:
        lines.append(f"  - {cand}  (score={sc:.3f})\n")
    hr.write_text("".join(lines))
    print(f"Healed {failing} -> {best}\nReport: {hr}")

if __name__ == "__main__":
    main()