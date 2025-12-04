#!/usr/bin/env python3
import json, os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.image as mpimg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, "config", "home_rois.json")
OUT = os.path.join(ROOT, "outputs", "bonvoy_annotated.png")

def denorm(box, W, H):
    x, y, w, h = box
    return x*W, y*H, w*W, h*H

def main():
    cfg = json.load(open(CFG, "r"))
    img_path = os.path.join(ROOT, cfg["image"])
    img = mpimg.imread(img_path)
    H, W = img.shape[0], img.shape[1]

    fig, ax = plt.subplots(figsize=(W/100, H/100), dpi=100)
    ax.imshow(img); ax.axis('off')

    # ROIs (blue)
    for r in cfg["rois"]:
        x,y,w,h = denorm(r["box"], W, H)
        rect = patches.Rectangle((x,y), w,h, linewidth=2, edgecolor='blue', facecolor='none')
        ax.add_patch(rect)
        ax.text(x, y-5, f'{r["key"]}', fontsize=10, color='blue', bbox=dict(facecolor='white', alpha=0.6, edgecolor='none'))

    # Masks (red dashed)
    for m in cfg.get("masks", []):
        x,y,w,h = denorm(m["box"], W, H)
        rect = patches.Rectangle((x,y), w,h, linewidth=2, edgecolor='red', linestyle='--', facecolor='none')
        ax.add_patch(rect)
        ax.text(x, y+h+12, f'MASK: {m["key"]}', fontsize=9, color='red', bbox=dict(facecolor='white', alpha=0.6, edgecolor='none'))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    plt.savefig(OUT, bbox_inches='tight', pad_inches=0)
    print(f"Annotated overlay saved to: {OUT}")

if __name__ == "__main__":
    main()