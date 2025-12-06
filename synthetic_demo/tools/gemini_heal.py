#!/usr/bin/env python3
import json, glob
from pathlib import Path
from llm.gemini_client import multimodal_heal_gemini

ROOT = Path(__file__).resolve().parents[1]
android_cat = ROOT / "config" / "selector_catalog.json"
plat_map    = ROOT / "config" / "platform_map.json"

# latest run
bundles = sorted(glob.glob(str(ROOT / "runs" / "run_*" / "bundle.json")))
if not bundles:
    raise SystemExit("No bundles found. Run simulate_run.py first.")
bundle_path = Path(bundles[-1])
b = json.loads(bundle_path.read_text())

failing_key = b.get("failing_label","unknown")
semantics   = Path(b["artifacts"]["semantics"]).read_text()
ios_tree    = (ROOT / "data" / "ios" / "accessibility_tree.json").read_text()
# Optional screenshot from the vision overlay (if present)
shot = ROOT.parents[1] / "vision_demo" / "outputs" / "bonvoy_annotated.png"
shot = shot if shot.exists() else None

suggest = multimodal_heal_gemini(failing_key, semantics, ios_tree, shot)
conf = suggest.get("confidence", 0.6)
print("Gemini suggests:", json.dumps(suggest, indent=2))

# Patch Android catalog
ac = json.loads(android_cat.read_text())
ac[failing_key] = {"testTag": suggest["android"]["testTag"]}
android_cat.write_text(json.dumps(ac, indent=2))

# Patch platform map (both platforms)
pm = json.loads(plat_map.read_text())
pm.setdefault(failing_key, {})
pm[failing_key]["android"] = {"testTag": suggest["android"]["testTag"]}
pm[failing_key]["ios"]     = {"accessibilityId": suggest["ios"]["accessibilityId"]}
plat_map.write_text(json.dumps(pm, indent=2))

# Write heal report
report = Path(bundle_path).parent / "heal_report.md"
report.write_text(
    "# Self-Heal Patch (Gemini 2.5)\n\n"
    f"- Failing key: `{failing_key}`\n"
    f"- Android → `testTag={suggest['android']['testTag']}`\n"
    f"- iOS → `accessibilityId={suggest['ios']['accessibilityId']}`\n"
    f"- Confidence: {conf:.2f}\n"
    f"- Rationale: {suggest.get('rationale','')}\n"
    f"- Files updated: selector_catalog.json, platform_map.json\n"
)
print("Heal report:", report)