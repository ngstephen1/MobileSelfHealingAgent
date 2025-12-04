# Self-Healing Test Agent — Conceptual Demo (Method 8)

Flow:
1) `tools/run_test.py` fails to find `btn.viewRates` → writes failure bundle in `reports/run_*`.
2) `tools/heal.py` discovers `btn.viewPrices` in semantics and updates `assets/selectors.json`.
3) Re-run test → PASS.

## Run
```bash
cd selfheal_demo
python3 tools/run_test.py     # FAIL + bundle
python3 tools/heal.py         # HEAL (update mapping)
python3 tools/run_test.py     # PASS