#!/usr/bin/env python3
import os, json, base64
from pathlib import Path
from typing import Optional, Dict, Any, List

# Lazy import to allow running without the SDK
def _sdk():
    import google.generativeai as genai
    return genai

GEMINI_MODEL_TXT = os.getenv("GEMINI_MODEL_TXT", "gemini-2.5-flash")   # fast, cheap
GEMINI_MODEL_PRO = os.getenv("GEMINI_MODEL_PRO", "gemini-2.5-pro") # stronger reasoning

def _configure():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    sdk = _sdk()
    sdk.configure(api_key=key)
    return sdk

def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""

def _b64img(p: Path) -> Dict[str, Any]:
    data = p.read_bytes()
    return {
        "inline_data": {
            "mime_type": "image/png" if p.suffix.lower()==".png" else "image/jpeg",
            "data": base64.b64encode(data).decode("utf-8")
        }
    }

def spec_to_feature_gemini(jira_md: str, steps_yaml: str, selector_catalog: Dict[str, Any],
                           platform_map: Dict[str, Any], locales: List[str]) -> str:
    """
    Ask Gemini to emit ONLY valid Gherkin using canonical phrases from steps.yaml and logical keys
    present in selector_catalog/platform_map. Platform-agnostic (glue maps per platform).
    """
    sdk = _configure()
    model = sdk.GenerativeModel(GEMINI_MODEL_PRO)

    prompt = f"""
You write Marriott Bonvoy mobile BDD in Gherkin.

Constraints:
- Reuse ONLY step phrases from steps.yaml (below).
- Use logical keys that exist in selector catalogs (below), not raw text.
- Parameterize values (city, dates, roomType); no hard-coded literals.
- Include tags: @regression @pilot_ai {' '.join('@'+loc for loc in locales)}
- Provide a Background for signed-in user with feature flags enabled.
- Main flow as a Scenario Outline with an Examples table (2–3 rows).
- Add one negative scenario (cancel at modal / unavailable roomType).
- Output: ONLY a valid .feature body (no commentary).

steps.yaml:
---
{steps_yaml}
---

selector_catalog (android):
---
{json.dumps(selector_catalog, indent=2)}
---

platform_map (ios + android logical alignment):
---
{json.dumps(platform_map, indent=2)}
---

Jira spec:
---
{jira_md}
---"""

    resp = model.generate_content(prompt)
    return resp.text.strip()

def multimodal_heal_gemini(failing_key: str,
                           android_semantics_txt: str,
                           ios_tree_json: str,
                           screenshot_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Ask Gemini to propose a better selector for failing_key using:
    - Android semantics dump (Jetpack Compose semantics)
    - iOS accessibility tree
    - Optional screenshot to ground the element location/text
    Returns: { "android": {"testTag": ...}, "ios": {"accessibilityId": ...}, "confidence": 0..1, "rationale": "..." }
    """
    sdk = _configure()
    model = sdk.GenerativeModel(GEMINI_MODEL_PRO)

    system = f"""You are a mobile QE healing assistant.
Task: For the failing logical key '{failing_key}', propose the most likely *stable* selectors for Android (Compose testTag) and iOS (XCUI accessibilityIdentifier).
Rules:
- Prefer existing canonical tags you see in the dumps.
- If the element text says 'View Prices', prefer keys that include 'viewPrices' rather than 'viewRates'.
- Return strict JSON only with keys: android.testTag, ios.accessibilityId, confidence (0..1), rationale (short)."""

    parts = [{"text": system},
             {"text": "\n\n[ANDROID_SEMANTICS]\n" + android_semantics_txt},
             {"text": "\n\n[IOS_ACCESSIBILITY_TREE]\n" + ios_tree_json}]
    if screenshot_path and screenshot_path.exists():
        parts.append(_b64img(screenshot_path))

    resp = model.generate_content(parts)

    # Try to parse JSON out of the response
    text = resp.text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        payload = text[start:end+1]
        try:
            data = json.loads(payload)
            # normalize
            out = {
                "android": {"testTag": data.get("android", {}).get("testTag")},
                "ios": {"accessibilityId": data.get("ios", {}).get("accessibilityId")},
                "confidence": float(data.get("confidence", 0.6)),
                "rationale": data.get("rationale", "")
            }
            return out
        except Exception:
            pass

    # Fallback simple heuristic if parsing fails
    guess = "btn.viewPrices" if "View Prices" in android_semantics_txt or "viewPrices" in ios_tree_json else failing_key
    return {
        "android": {"testTag": guess},
        "ios": {"accessibilityId": guess},
        "confidence": 0.61,
        "rationale": "Heuristic fallback: text contains 'Prices'."
    }