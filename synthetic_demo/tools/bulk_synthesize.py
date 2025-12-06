#!/usr/bin/env python3
import json, random, time, argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
DATA = ROOT / "data"
DATA.mkdir(parents=True, exist_ok=True)

ALIASES = {
  "btn.viewRates": ["btn.viewPrices", "btn.viewRate", "btn.pricesNow"],
  "btn.bookNow":   ["btn.reserve", "btn.reserveNow"],
  "tab.trips":     ["home.tab.trips", "tab.myTrips"],
}
LOCALES = ["en_US","es_ES","de_DE","fr_FR","ar_SA"]
DEVICES = ["Google Pixel 7 Pro","Samsung S22","iPhone 14","iPhone 15 Pro"]

SEM_TEMPLATE = """Root
  Node: Screen TestTag='screen.searchResults'
  Node: Button Text='{text}' TestTag='{testTag}' ContentDesc='{content}' clickable={click} visible={vis}
"""

def write_ios_tree(dirp: Path, tag: str, text: str):
    ios = {
      "screen": "searchResults",
      "elements": [
        {"role": "button", "label": text, "accessibilityId": tag, "enabled": True}
      ]
    }
    (dirp/"ios_tree.json").write_text(json.dumps(ios, indent=2))

def write_bundle(dirp: Path, failing_key: str, chosen: str):
    b = {
      "test": "Synthetic::ModifyRoom",
      "failing_label": failing_key,
      "message": f"Missing tag in semantics for key={failing_key}, testTag={chosen}",
      "artifacts": {
        "semantics": str(dirp / "semantics.txt"),
        "uiauto": str(dirp / "uiauto.xml"),
        "screenshot": str(dirp / "screenshot.txt")
      }
    }
    (dirp/"bundle.json").write_text(json.dumps(b, indent=2))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=50)
    ap.add_argument("--locales", nargs="*", default=LOCALES)
    ap.add_argument("--devices", nargs="*", default=DEVICES)
    args = ap.parse_args()

    for i in range(args.count):
        ts = time.strftime("%Y%m%d_%H%M%S")
        dirp = RUNS / f"run_{ts}_{i:03d}"
        dirp.mkdir(parents=True, exist_ok=True)
        failing = random.choice(list(ALIASES.keys()))
        correct = random.choice(ALIASES[failing])
        # semantics, ios, uiauto, screenshot placeholders
        text = "View Prices" if "Prices" in correct or "prices" in correct else "View Rates"
        sem = SEM_TEMPLATE.format(text=text, testTag=correct, content=f"View current {text.lower()}", click="true", vis="true")
        (dirp/"semantics.txt").write_text(sem)
        (dirp/"uiauto.xml").write_text("<hierarchy></hierarchy>")
        (dirp/"screenshot.txt").write_text(f"[device={random.choice(args.devices)}][locale={random.choice(args.locales)}]")
        write_ios_tree(dirp, correct, text)
        write_bundle(dirp, failing, correct)

    print(f"Generated {args.count} synthetic failure bundles in {RUNS}")

if __name__ == "__main__":
    main()