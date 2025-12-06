#!/usr/bin/env python3
import csv, json, glob
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HIST = ROOT / "runs" / "history.csv"

def main():
    rows = []
    for bpath in glob.glob(str(ROOT/"runs"/"run_*"/"bundle.json")):
        run = Path(bpath).parent
        hr = run/"heal_report.md"
        status = "unknown"
        chosen = ""
        confidence = ""
        if hr.exists():
            txt = hr.read_text()
            # naive parse
            for line in txt.splitlines():
                if line.startswith("- Chosen:"):
                    chosen = line.split("`")[1]
                if "conf=" in line:
                    m = line.split("conf=")[-1].split()[0]
                    confidence = m.strip().strip(")")[:6]
        rows.append([run.name, json.loads(Path(bpath).read_text()).get("failing_label"), chosen, confidence])

    HIST.parent.mkdir(parents=True, exist_ok=True)
    with HIST.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["run","failing_key","chosen_key","confidence"])
        w.writerows(rows)
    print("Wrote", HIST)

if __name__ == "__main__":
    main()