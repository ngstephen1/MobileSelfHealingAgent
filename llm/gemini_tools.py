# llm/gemini_tools.py
#!/usr/bin/env python3
import os, json, textwrap
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

try:
    import google.generativeai as genai
except Exception:
    genai = None  # we’ll graceful-fallback if missing

REPO = Path(__file__).resolve().parents[1]
SYN_ROOT = REPO / "synthetic_demo"
SYN_CFG = SYN_ROOT / "config" / "selector_catalog.json"
PLAT_MAP = SYN_ROOT / "config" / "platform_map.json"
BDD_DIR = SYN_ROOT / "bdd"
FEATURES_DIR = BDD_DIR / "features"
STEPS_PATH = BDD_DIR / "steps.yaml"
STYLE_GUIDE = BDD_DIR / "style_guide.md"
JIRA_SPEC = SYN_ROOT / "jira_case.md"
RUNS_DIR = SYN_ROOT / "runs"

DEFAULT_MODEL = os.getenv("GEMINI_MODEL_PRO", "gemini-2.5-pro")

def _safe_read(path: Path) -> str:
    try:
        return path.read_text()
    except Exception:
        return ""

def _safe_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}

def load_context() -> Dict[str, Any]:
    ctx = {
        "steps": _safe_read(STEPS_PATH),
        "style": _safe_read(STYLE_GUIDE),
        "jira": _safe_read(JIRA_SPEC),
        "selector_catalog": _safe_json(SYN_CFG),
        "platform_map": _safe_json(PLAT_MAP),
        "features": [],
    }
    if FEATURES_DIR.exists():
        for f in sorted(FEATURES_DIR.glob("*.feature")):
            try:
                ctx["features"].append({"path": str(f), "text": f.read_text()})
            except Exception:
                pass
    return ctx

def latest_run_folder() -> Optional[Path]:
    if not RUNS_DIR.exists():
        return None
    runs = sorted([p for p in RUNS_DIR.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime)
    return runs[-1] if runs else None

def load_latest_failure_bundle() -> Dict[str, Any]:
    run = latest_run_folder()
    if not run:
        return {}
    data = {"run_dir": str(run)}
    for name in ["bundle.json", "heal_report.md", "browserstack_run.json", "qmetry_update.json",
                 "semantics.txt", "uiauto.xml", "screenshot.txt", "ios_tree.json"]:
        p = run / name
        data[name] = _safe_read(p) if name.endswith((".md",".txt",".xml",".json")) else ""
        if name.endswith(".json"):
            try:
                data[name] = json.loads((run / name).read_text())
            except Exception:
                pass
    return data

def _ensure_gemini():
    if genai is None:
        raise RuntimeError("google-generativeai is not installed. Run: pip install google-generativeai")
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set. Export it or paste it in the Streamlit sidebar.")
    genai.configure(api_key=key)

def _model(system_instruction: str):
    _ensure_gemini()
    return genai.GenerativeModel(
        model_name=DEFAULT_MODEL,
        system_instruction=system_instruction,
    )

def _truncate(text: str, max_chars: int = 12000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[...truncated...]"

# ---------- High-level tasks ----------

def chat_answer(user_msg: str, extra_context: Dict[str, Any]) -> str:
    """
    General QA chat grounded on repo artifacts.
    """
    sys_prompt = textwrap.dedent(f"""
    You are a senior QE assistant for the Marriott Bonvoy mobile app (Android + iOS).
    You write Gherkin BDD scenarios using canonical phrases from steps.yaml, and you
    propose stable selectors (Android testTag, iOS accessibilityIdentifier). Favor
    parameterization over literals. Be concise and specific. If asked for code, return
    only code fenced with triple backticks in the requested language.

    You can reference the following context snippets, but do not rewrite large files inline:
    - steps.yaml (canonical phrases)
    - selector_catalog.json (Android testTag mapping)
    - platform_map.json (Android ↔ iOS selector parity)
    - golden .feature files (examples of style/phrasing)
    - latest failure bundle (semantics, iOS tree, logs)
    """).strip()

    ctx = extra_context or {}
    steps = ctx.get("steps","")
    style = ctx.get("style","")
    jira = ctx.get("jira","")
    sel  = json.dumps(ctx.get("selector_catalog",{}), indent=2)[:6000]
    plat = json.dumps(ctx.get("platform_map",{}), indent=2)[:6000]

    features_join = "\n\n".join(
        [f"### {Path(f['path']).name}\n{_truncate(f['text'], 4000)}" for f in ctx.get("features", [])[:5]]
    )

    latest = load_latest_failure_bundle()
    latest_slim = ""
    if latest:
        b = latest.get("bundle.json", {})
        sem = latest.get("semantics.txt","")
        ios = latest.get("ios_tree.json", {})
        latest_slim = f"Latest bundle: {json.dumps(b)[:1500]}\n\nSemantics (head):\n{_truncate(sem, 1500)}\n\niOS tree:\n{_truncate(json.dumps(ios), 1500)}"

    parts = [
        {"text": f"[User]\n{user_msg}".strip()},
        {"text": f"[steps.yaml]\n{_truncate(steps, 4000)}"},
        {"text": f"[style_guide.md]\n{_truncate(style, 3000)}"},
        {"text": f"[selector_catalog.json]\n{sel}"},
        {"text": f"[platform_map.json]\n{plat}"},
        {"text": f"[golden_features]\n{_truncate(features_join, 8000)}"},
        {"text": f"[latest_failure_bundle]\n{_truncate(latest_slim, 4000)}"},
        {"text": f"[jira]\n{_truncate(jira, 4000)}"},
    ]
    mdl = _model(sys_prompt)
    resp = mdl.generate_content(parts)
    return resp.text.strip()

def spec_to_feature_from_jira(jira_text: str, steps: str, style: str, features: List[Dict[str,str]]) -> str:
    sys_prompt = textwrap.dedent("""
    You write production-ready Gherkin .feature files for the Marriott Bonvoy mobile app.
    Constraints:
    - Reuse canonical phrases from steps.yaml only
    - Prefer Android testTag over visible text; parameterize literals
    - Include tags (@regression @pilot_ai @en_US by default unless specified)
    - Use Scenario Outline + Examples table when values repeat
    """).strip()
    examples = "\n\n".join(
        [f"### {Path(f['path']).name}\n{_truncate(f['text'], 3000)}" for f in features[:3]]
    )
    content = [
        {"text": f"[Jira]\n{_truncate(jira_text, 6000)}"},
        {"text": f"[steps.yaml]\n{_truncate(steps, 5000)}"},
        {"text": f"[style_guide.md]\n{_truncate(style, 3000)}"},
        {"text": f"[golden_features]\n{examples}"},
        {"text": "Return ONLY valid .feature content. No commentary."}
    ]
    mdl = _model(sys_prompt)
    resp = mdl.generate_content(content)
    return resp.text.strip()

def heal_from_bundle(failing_key: str, sem_txt: str, ios_json: Dict[str,Any]) -> Dict[str, Any]:
    """
    Ask Gemini for cross-platform rebind. Return structured JSON:
    { "android": {"testTag": "..."}, "ios": {"accessibilityId": "..."}, "confidence": 0.0, "rationale": "..." }
    """
    sys_prompt = textwrap.dedent("""
    You are a mobile QE healing assistant. From semantics and iOS accessibility trees,
    propose a stable cross-platform selector rebind for the failing logical key.
    Prefer Android Jetpack Compose testTag and iOS accessibilityIdentifier.
    Return strictly JSON with fields: android.testTag, ios.accessibilityId, confidence (0..1), rationale.
    """).strip()
    mdl = _model(sys_prompt)
    resp = mdl.generate_content([
        {"text": f"[Failing key]\n{failing_key}"},
        {"text": f"[Semantics.txt]\n{_truncate(sem_txt, 8000)}"},
        {"text": f"[iOS tree]\n{_truncate(json.dumps(ios_json), 6000)}"},
        {"text": "Return ONLY minified JSON."}
    ])
    txt = resp.text.strip()
    try:
        if "```" in txt:
            txt = txt.split("```")[1].strip("json").strip()
        data = json.loads(txt)
        return data
    except Exception:
        return {
            "android": {"testTag": failing_key},
            "ios": {"accessibilityId": failing_key},
            "confidence": 0.5,
            "rationale": "Fallback: could not parse model output."
        }

def risk_matrix_from_change(change_hint: str, locales=None, devices=None) -> str:
    """
    Build a small device × locale risk matrix plan via Gemini.
    """
    sys_prompt = "You are a QA planner. Build a small, prioritized device×locale matrix as Markdown."
    locales = locales or ["en_US","es_ES","de_DE","fr_FR","ar_SA"]
    devices = devices or ["Pixel 7 Pro","Samsung S22","iPhone 14","iPhone 15 Pro"]
    mdl = _model(sys_prompt)
    resp = mdl.generate_content([
        {"text": f"[Change list]\n{change_hint}"},
        {"text": f"Locales available: {', '.join(locales)}"},
        {"text": f"Devices available: {', '.join(devices)}"},
        {"text": "Return Markdown table with 6–12 cells and short rationale."}
    ])
    return resp.text.strip()