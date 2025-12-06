#!/usr/bin/env python3
import os, re, json, glob, subprocess
from math import exp
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAT  = ROOT / "config" / "selector_catalog.json"

# Direct aliases for known UI renames (expand as you discover more)
ALIASES = {
  "btn.viewRates": ["btn.viewPrices"]
}

def parse_tags(sem_path):
    txt = Path(sem_path).read_text(encoding="utf-8", errors="ignore")
    tags = re.findall(r"TestTag\s*=\s*'([^']+)'", txt)
    return set(tags), txt

def lev(a,b):
    a,b=a.lower(),b.lower()
    dp=list(range(len(b)+1))
    for i,ca in enumerate(a,1):
        prev=dp[0]; dp[0]=i
        for j,cb in enumerate(b,1):
            cur=dp[j]; dp[j]=min(dp[j]+1, dp[j-1]+1, prev+(0 if ca==cb else 1)); prev=cur
    return dp[-1]

def clickable_boost(tag, txt):
    # crude: look for the tag on a line that mentions clickable=true
    pat = rf"{re.escape(tag)}.*clickable\s*=\s*true"
    return 1.0 if re.search(pat, txt, re.I|re.S) else 0.7

def conf(tag, key, txt):
    sim     = 1/(1+lev(tag,key))
    in_ctx  = 1.0 if ("screen.searchResults" in txt or "screen.home" in txt) else 0.7
    click   = clickable_boost(tag, txt)
    raw = 0.55*sim + 0.25*in_ctx + 0.20*click
    # logistic squashing
    return 1/(1+exp(-6*(raw-0.5)))

def visual_fallback(key):
    vc = ROOT.parent / "vision_demo" / "tools" / "visual_heal.py"
    if not vc.exists(): return None, 0.0, "visual tool missing"
    r = subprocess.run(["python3", str(vc), key], capture_output=True, text=True)
    m = re.search(r"testTag=([A-Za-z0-9\.\-_]+).*confidence\s+([0-9.]+)", r.stdout)
    if not m: return None, 0.0, "visual parse fail"
    return m.group(1), float(m.group(2)), "visual"

if __name__ == "__main__":
    bundles = sorted(glob.glob(str(ROOT / "runs" / "run_*" / "bundle.json")), key=os.path.getmtime)
    if not bundles: raise SystemExit("No bundles found. Run simulate_run.py to create one.")
    bundle_path = bundles[-1]
    b = json.loads(Path(bundle_path).read_text())
    key = b.get("failing_label","unknown")
    sem = b["artifacts"]["semantics"]

    # 1) Semantic candidates
    tags, txt = parse_tags(sem)
    pick, score, mode = None, 0.0, "semantic"
    if tags:
        # alias fast-path
        for alias in ALIASES.get(key, []):
            if alias in tags:
                pick, score = alias, 0.93
                break
        if not pick:
            ranked = sorted([(t, conf(t,key,txt)) for t in tags], key=lambda x: x[1], reverse=True)
            pick, score = ranked[0]

    # 2) If weak, try vision fallback
    SEMANTIC_THRESHOLD = 0.55   # was 0.70; friendlier for small renames
    if not pick or score < SEMANTIC_THRESHOLD:
        vtag, vconf, vmode = visual_fallback(key)
        if vtag and vconf > score:
            pick, score, mode = vtag, vconf, vmode

    if not pick:
        raise SystemExit("No candidate selector found; manual review needed.")

    # 3) Patch catalog
    cat = json.loads(CAT.read_text())
    cat[key] = {"testTag": pick}
    CAT.write_text(json.dumps(cat, indent=2))

    # 4) Report into the same run folder
    report = Path(bundle_path).parent / "heal_report.md"
    report.write_text(
        "# Self-Heal Patch\n\n"
        f"- Failing key: `{key}`\n"
        f"- Proposed: `testTag={pick}` (source={mode}, confidence={score:.2f})\n"
        f"- Updated: synthetic_demo/config/selector_catalog.json\n"
    )
    print(f"Healed {key} -> {pick} (mode={mode}, conf={score:.2f})")