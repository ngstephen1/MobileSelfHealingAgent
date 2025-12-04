#!/usr/bin/env python3
import os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def run(cmd):
    print(f"$ {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=os.path.join(ROOT, "tools"))
    if res.returncode != 0:
        sys.exit(res.returncode)

if __name__ == "__main__":
    run(["python3", "annotate_rois.py"])
    run(["python3", "generate_selectors.py"])
    run(["python3", "truncation_probe.py"])
    # demo propose heal for an unknown target:
    run(["python3", "visual_heal.py", "tab.experiences"])
    
   
