#!/usr/bin/env python3
import json, os, sys, concurrent.futures, subprocess, time
from pathlib import Path

# Ensure repo root on sys.path so we can import llm.*
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

def call_with_timeout(fn, timeout_s, *args, **kwargs):
    """Execute fn(*args, **kwargs) with a hard timeout in seconds."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn, *args, **kwargs)
        try:
            return fut.result(timeout=timeout_s)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(f"Gemini call timed out after {timeout_s}s")

def has_gemini_key() -> bool:
    return bool(os.getenv("GEMINI_API_KEY"))

def local_fallback(out_path: Path) -> str:
    """
    If Gemini isn't available or times out, generate a reasonable .feature:
    - Prefer the local generator `generate_feature.py` if present
    - Otherwise write a small, valid Gherkin stub
    Returns a short string label describing the fallback used.
    """
    # Prefer local generator to stay consistent with your synthetic flow
    gen = Path(__file__).resolve().parent / "generate_feature.py"
    if gen.exists():
        res = subprocess.run([sys.executable, str(gen)], capture_output=True, text=True)
        if res.returncode == 0:
            src = out_path.parent / "TC_APP_ModifyRoom.feature"
            if src.exists():
                out_path.write_text(src.read_text())
                return "fallback:local-generator"

    # Minimal, valid Gherkin stub
    stub = (
        "@regression @en_US @pilot_ai\n"
        "Feature: Modify Room Type (fallback)\n\n"
        "Background:\n"
        "  Given user signs in as \"dynamicUser\"\n"
        "  And user enables feature flag \"QuickSearch\"\n\n"
        "Scenario Outline: Modify room type\n"
        "  When user opens \"Trips\" tab\n"
        "  Then user verify \"Trips\" page\n"
        "  When user taps on \"currentReservation\" button\n"
        "  Then user verify \"Stay\" page\n"
        "  When user taps on \"stay.modify.link\" button\n"
        "  Then user sees \"Modify Your Reservation?\" modal\n"
        "  When user taps on \"btn.continue\" button\n"
        "  Then user verify \"Room List\" page\n"
        "  When user selects \"opt.viewRate\" option\n"
        "  Then user verify \"Rate Type\" page\n"
        "  When user selects \"rate.any\" rate\n"
        "  Then user verify \"Confirm Changes\" page\n"
        "  When user taps on \"btn.bookNow\" button\n"
        "  Then booking is completed\n\n"
        "Examples:\n"
        "  | city     | checkIn     | checkOut    | roomType |\n"
        "  | Boston   | 2025-12-20  | 2025-12-22  | Flexible |\n"
        "  | New York | 2026-01-05  | 2026-01-07  | Flexible |\n"
    )
    out_path.write_text(stub)
    return "fallback:stub"

def main():
    ROOT = Path(__file__).resolve().parents[1]
    jira = (ROOT / "jira_case.md").read_text()
    steps = (ROOT / "bdd" / "steps.yaml").read_text()
    selector_catalog = json.loads((ROOT / "config" / "selector_catalog.json").read_text())
    platform_map_path = ROOT / "config" / "platform_map.json"
    platform_map = json.loads(platform_map_path.read_text()) if platform_map_path.exists() else {}

    out_path = ROOT / "bdd" / "features" / "TC_APP_ModifyRoom_gemini.feature"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Allow configurable timeout via env; default 45s
    timeout_s = int(os.getenv("GEMINI_TIMEOUT_S", "45"))

    if not has_gemini_key():
        mode = local_fallback(out_path)
        print(f"No GEMINI_API_KEY; wrote fallback feature: {out_path} ({mode})")
        return

    # Import here after adjusting sys.path
    from llm.gemini_client import spec_to_feature_gemini

    print(f"Calling Gemini (timeout={timeout_s}s) …")
    try:
        feature = call_with_timeout(
            spec_to_feature_gemini,
            timeout_s,
            jira, steps, selector_catalog, platform_map, ["en_US","es_ES"]
        )
        # Basic sanity: ensure it looks like Gherkin
        if "Scenario" not in feature and "Feature" not in feature:
            raise ValueError("Gemini response did not look like Gherkin.")
        out_path.write_text(feature)
        print("Gemini feature generated:", out_path)
    except Exception as e:
        print(f"[WARN] Gemini generation failed: {e}")
        mode = local_fallback(out_path)
        print(f"Used {mode}; wrote:", out_path)

if __name__ == "__main__":
    main()