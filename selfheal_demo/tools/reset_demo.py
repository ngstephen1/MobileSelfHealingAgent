#!/usr/bin/env python3
import os, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SELECTORS = os.path.join(ROOT, "assets", "selectors.json")
json.dump({
  "btn.viewRates": {"testTag": "btn.viewRates"},
  "screen.searchResults": {"testTag": "screen.searchResults"}
}, open(SELECTORS, "w"), indent=2)
print("Reset demo: selectors.json restored to failing mapping.")