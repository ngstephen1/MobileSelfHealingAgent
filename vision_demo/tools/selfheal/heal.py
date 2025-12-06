#!/usr/bin/env python3
import os, json, re, glob, subprocess
from math import exp
from pathlib import Path

# ---- Paths
ROOT = Path(__file__).resolve().parent.parent
ANDROID_SELECTORS = ROOT / "app" / "src" / "androidTest" / "assets" / "selfheal" / "selectors.json"
BUNDLES = list(sorted(Path(".").glob("**/selfheal/**/bundle.json"), key=os.path.getmtime))

# ---- Utils
def parse_semantics(sem_path):
    txt = Path(sem_path).read_text(encoding="utf-8", errors="ignore") if Path(sem_path).exists() else ""
    tags = re.findall(r"TestTag\s*=\s*'([^']+)'", txt)
    return set(tags), txt

def levenshtein(a,b):
    a,b=a.lower(),b.lower()
    dp=list(range(len(b)+1))
    for i,ca in enumerate(a,1):
        prev=dp[0]; dp[0]=i
        for j,cb in enumerate(b,1):
            cur=dp[j]
            dp[j]=min(dp[j]+1, dp[j-1]+1, prev+(0 if ca==cb else 1))
            prev=cur
    return dp[-1]

def conf_score(tag, key, txt):
    sim = 1/(1+levenshtein(tag, key))
    in_ctx = 1.0 if "screen.searchResults" in txt or "screen.home" in txt else 0.7
    raw = 0.7*sim + 0.3*in_ctx
    return 1/(1+exp(-6*(raw-0.5)))  # 0..1

def choose_semantic(sem_path, failing_key):
    tags, txt = parse_semantics(sem_path)
    if not tags: return None, 0.0, "no semantic tags", txt
    ranked = sorted([(t, conf_score(t, failing_key, txt)) for t in tags], key=lambda x: x[1], reverse=True)
    return ranked[0][0], ranked[0][1], "semantic", txt

def choose_visual(failing_key):
    vc = ROOT / "vision_demo" / "tools" / "visual_heal.py"
    if not vc.exists(): return None, 0.0, "no visual tool"
    res = subprocess.run(["python3", str(vc), failing_key], capture_output=True, text=True)
    m = re.search(r"testTag=([A-Za-z0-9\.\-_]+).*confidence\s+([0-9.]+)", res.stdout)
    if not m: return None, 0.0, "visual parse failed"
    return m.group(1), float(m.group(2)), "visual"

def patch_selectors(key, new_tag):
    ANDROID_SELECTORS.parent.mkdir(parents=True, exist_ok=True)
    sel = {}
    if ANDROID_SELECTORS.exists():
        try: sel = json.loads(ANDROID_SELECTORS.read_text())
        except: sel = {}
    sel[key] = {"testTag": new_tag}
    ANDROID_SELECTORS.write_text(json.dumps(sel, indent=2))
    return ANDROID_SELECTORS

def write_report(folder, key, picked_tag, mode, conf):
    p = Path(folder) / "heal_report.md"
    p.write_text(
        "# Self-Heal Patch\n\n"
        f"- Failing key: `{key}`\n"
        f"- Proposed selector: `testTag={picked_tag}`\n"
        f"- Source: {mode}, confidence {conf:.2f}\n"
        f"- Updated: `{ANDROID_SELECTORS}`\n"
    )
    return p

if __name__ == "__main__":
    if not BUNDLES:
        print("No failure bundles; nothing to heal.")
        raise SystemExit(0)
    bundle_path = BUNDLES[-1]
    bundle = json.loads(Path(bundle_path).read_text())
    key = bundle.get("failing_label", "unknown")
    sem = bundle["artifacts"]["semantics"]

    # Try semantics first
    tag, conf, mode, txt = choose_semantic(sem, key)
    # If low-confidence or missing, try vision fallback
    if not tag or conf < 0.70:
        vtag, vconf, vmode = choose_visual(key)
        if vtag and vconf > conf:
            tag, conf, mode = vtag, vconf, vmode

    if not tag:
        print("No candidate selector found. Leaving for manual triage.")
        raise SystemExit(1)

    out_file = patch_selectors(key, tag)
    report = write_report(Path(bundle_path).parent, key, tag, mode, conf)

    print("== Healer ==")
    print(f"- Bundle: {bundle_path}")
    print(f"- Fix: {key} -> {tag} (source={mode}, confidence={conf:.2f})")
    print(f"- Updated: {out_file}")
    print(f"- Report: {report}")