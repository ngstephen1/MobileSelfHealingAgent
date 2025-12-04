#!/usr/bin/env python3
import os, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = os.path.join(ROOT, "outputs", "selectors.json")
dst = os.path.join(ROOT, "..", "app", "src", "androidTest", "assets", "selfheal", "selectors.json")

def main():
    if not os.path.exists(src):
        raise SystemExit("Missing outputs/selectors.json. Run generate_selectors.py first.")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    new = json.load(open(src))
    merged = {}
    if os.path.exists(dst):
        try: merged = json.load(open(dst))
        except: merged = {}
    merged.update(new)  # prefer new home.* tags
    json.dump(merged, open(dst, "w"), indent=2)
    print(f"Promoted {len(new)} selectors → {dst}")

if __name__ == "__main__":
    main()