#!/usr/bin/env python3
import json, os, math
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.image as mpimg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, "config", "home_rois.json")
IMG = os.path.join(ROOT, "assets", "bonvoy.png")
OUT = os.path.join(ROOT, "outputs", "bonvoy_truncation_overlay.png")

# crude width model: width_px ≈ len(text) * font_px * k
K = 0.55  # average width factor
FONT_PX = 36  # assumed font size for UI labels; tune per component

def denorm(box, W, H): x,y,w,h = box; return x*W, y*H, w*W, h*H

def main(scale=1.35):
    cfg = json.load(open(CFG, "r"))
    img = mpimg.imread(IMG)
    H, W = img.shape[0], img.shape[1]

    fig, ax = plt.subplots(figsize=(W/100, H/100), dpi=100)
    ax.imshow(img); ax.axis('off')

    violations = []
    for r in cfg["rois"]:
        label = r.get("label", "")
        if not label: continue  # skip unlabeled items

        x,y,w,h = denorm(r["box"], W, H)
        est_width = len(label) * FONT_PX * K * scale  # expanded text width
        if est_width > w * 0.95:  # overflow
            violations.append((r["key"], est_width, w))
            # draw red overlay
            rect = patches.Rectangle((x,y), w,h, linewidth=0, facecolor='red', alpha=0.25)
            ax.add_patch(rect)
            ax.text(x+4, y+h/2, f'{r["key"]} overflow', fontsize=10, color='white', va='center')

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    plt.savefig(OUT, bbox_inches='tight', pad_inches=0)
    print(f"Truncation overlay saved to: {OUT}")
    if violations:
        print("⚠ Possible truncations (scale={:.2f}):".format(scale))
        for k, ew, ww in violations:
            print(f" - {k}: est {int(ew)}px > box {int(ww)}px")
    else:
        print("No truncation detected at this scale.")

if __name__ == "__main__":
    # Change the scale to simulate German/Arabic stretch (e.g., 1.2–1.4)
    main(scale=1.35)