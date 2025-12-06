#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bonvoy Self-Healing QE Demo (Synthetic) + Gemini 2.5 QA Copilot
Single Streamlit app that includes:
 - Workflow (Generate ➜ Fail ➜ Heal ➜ Re-run ➜ BrowserStack/QMetry ➜ Report)
 - Metrics (history, confidence charts)
 - Chatbot (Gemini 2.5): BDD authoring, heal proposals, risk matrix, artifact Q&A

This file is self-contained (no extra project files required for the chat).
"""
import os, sys, json, subprocess, time, difflib, textwrap
from pathlib import Path
from typing import Dict, Any, List, Optional

import streamlit as st
try:
    import pandas as pd  # used in Metrics tab
except Exception:
    pd = None

# Optional LLM import (graceful fallback)
try:
    import google.generativeai as genai
except Exception:
    genai = None

# ---------- Paths ----------
REPO = Path(__file__).resolve().parents[1]
SYN_ROOT = REPO / "synthetic_demo"
SYN_TOOLS = SYN_ROOT / "tools"
SYN_RUNS = SYN_ROOT / "runs"
SYN_CFG = SYN_ROOT / "config" / "selector_catalog.json"
PLAT_MAP = SYN_ROOT / "config" / "platform_map.json"
BDD_DIR = SYN_ROOT / "bdd"
FEATURES_DIR = BDD_DIR / "features"
STEPS_PATH = BDD_DIR / "steps.yaml"
STYLE_GUIDE = BDD_DIR / "style_guide.md"
JIRA_SPEC = SYN_ROOT / "jira_case.md"

VIS_ROOT = REPO / "vision_demo"
VIS_TOOLS = VIS_ROOT / "tools"
VIS_OUT = VIS_ROOT / "outputs"
VIS_IMG_ANN = VIS_OUT / "bonvoy_annotated.png"
VIS_IMG_TRUNC = VIS_OUT / "bonvoy_truncation_overlay.png"

# ---------- Small FS helpers ----------
def run_tool(pyfile: Path, cwd: Path):
    if not pyfile.exists():
        return False, f"Missing: {pyfile}"
    proc = subprocess.run(
        ["python3", str(pyfile)],
        cwd=str(cwd),
        capture_output=True,
        text=True
    )
    ok = (proc.returncode == 0)
    out = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    return ok, out.strip()

def run_tool_with_args(pyfile: Path, cwd: Path, args: List[str]):
    if not pyfile.exists():
        return False, f"Missing: {pyfile}"
    proc = subprocess.run(
        ["python3", str(pyfile), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True
    )
    ok = (proc.returncode == 0)
    out = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    return ok, out.strip()

def latest_run_folder() -> Optional[Path]:
    if not SYN_RUNS.exists():
        return None
    runs = sorted([p for p in SYN_RUNS.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime)
    return runs[-1] if runs else None

def load_json(path: Path):
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception as e:
        return {"error": str(e), "raw": path.read_text() if path.exists() else ""}

def read_text(path: Path, max_chars: int = 12000):
    try:
        txt = path.read_text()
        return txt if len(txt) <= max_chars else txt[:max_chars] + "\n\n[...truncated...]"
    except Exception:
        return ""

def selector_status():
    try:
        d = json.loads(SYN_CFG.read_text())
        return d.get("btn.viewRates")
    except Exception:
        return None

def ensure_vision_inputs():
    # Make sure the screenshot is in place
    candidates = [
        VIS_ROOT / "assets" / "bonvoy.png",
        VIS_ROOT / "assets" / "bonvoy.PNG",
        REPO / "bonvoy.png",
        REPO / "bonvoy.PNG",
    ]
    for c in candidates:
        if c.exists():
            # if screenshot lives at repo root, copy to expected path
            if c.parent == REPO:
                (VIS_ROOT / "assets").mkdir(parents=True, exist_ok=True)
                (VIS_ROOT / "assets" / "bonvoy.png").write_bytes(c.read_bytes())
            return True
    return False

def json_diff(before_obj, after_obj) -> str:
    before = json.dumps(before_obj, indent=2).splitlines()
    after = json.dumps(after_obj, indent=2).splitlines()
    return "\n".join(difflib.unified_diff(before, after, fromfile="before", tofile="after", lineterm=""))

# ---------- Gemini helpers (self-contained) ----------
def _ensure_gemini():
    if genai is None:
        raise RuntimeError("google-generativeai is not installed. Run: pip install google-generativeai")
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set. Paste it in the sidebar.")
    genai.configure(api_key=key)

def _gem_model(sys_instruction: str):
    _ensure_gemini()
    model_name = os.getenv("GEMINI_MODEL_PRO", "gemini-2.5-pro")
    return genai.GenerativeModel(model_name=model_name, system_instruction=sys_instruction)

def _truncate(text: str, max_chars: int = 12000) -> str:
    return text if len(text) <= max_chars else (text[:max_chars] + "\n\n[...truncated...]")

def load_context() -> Dict[str, Any]:
    ctx: Dict[str, Any] = {
        "steps": read_text(STEPS_PATH),
        "style": read_text(STYLE_GUIDE),
        "jira": read_text(JIRA_SPEC),
        "selector_catalog": load_json(SYN_CFG) or {},
        "platform_map": load_json(PLAT_MAP) or {},
        "features": [],
    }
    if FEATURES_DIR.exists():
        for f in sorted(FEATURES_DIR.glob("*.feature")):
            try:
                ctx["features"].append({"path": str(f), "text": read_text(f)})
            except Exception:
                pass
    return ctx

def load_latest_failure_bundle() -> Dict[str, Any]:
    run = latest_run_folder()
    if not run:
        return {}
    data: Dict[str, Any] = {"run_dir": str(run)}
    # try typical artifacts
    for name in ["bundle.json", "heal_report.md", "browserstack_run.json", "qmetry_update.json",
                 "semantics.txt", "uiauto.xml", "screenshot.txt", "ios_tree.json"]:
        p = run / name
        if not p.exists():
            continue
        if name.endswith(".json"):
            try:
                data[name] = json.loads(p.read_text())
            except Exception:
                data[name] = read_text(p)
        else:
            data[name] = read_text(p)
    return data

def chat_answer(user_msg: str, extra_ctx: Dict[str, Any]) -> str:
    sys_prompt = textwrap.dedent("""
    You are a senior QE assistant for the Marriott Bonvoy mobile app (Android + iOS).
    You can: draft BDD in Gherkin using canonical phrases from steps.yaml; propose locator heals
    (Android testTag + iOS accessibilityIdentifier); build risk-based device×locale plans; and summarize artifacts.
    Be concise and specific. If the user asks for code, return only fenced code.
    """).strip()

    ctx = load_context()  # load fresh
    # Slim the context by flags in extra_ctx
    use_steps  = extra_ctx.get("use_steps", True)
    use_style  = extra_ctx.get("use_style", True)
    use_feats  = extra_ctx.get("use_feats", True)
    use_sel    = extra_ctx.get("use_sel", True)
    use_bundle = extra_ctx.get("use_bundle", True)
    use_jira   = extra_ctx.get("use_jira", True)

    parts: List[Dict[str, str]] = [{"text": f"[User]\n{user_msg}"}]
    if use_steps:  parts.append({"text": f"[steps.yaml]\n{_truncate(ctx.get('steps',''), 4000)}"})
    if use_style:  parts.append({"text": f"[style_guide.md]\n{_truncate(ctx.get('style',''), 3000)}"})
    if use_sel:
        parts.append({"text": f"[selector_catalog.json]\n{_truncate(json.dumps(ctx.get('selector_catalog',{}), indent=2), 6000)}"})
        parts.append({"text": f"[platform_map.json]\n{_truncate(json.dumps(ctx.get('platform_map',{}), indent=2), 6000)}"})
    if use_feats:
        features_join = "\n\n".join(
            [f"### {Path(f['path']).name}\n{_truncate(f['text'], 3000)}" for f in ctx.get("features", [])[:5]]
        )
        parts.append({"text": f"[golden_features]\n{_truncate(features_join, 8000)}"})
    if use_bundle:
        latest = load_latest_failure_bundle()
        if latest:
            b = latest.get("bundle.json", {})
            sem = latest.get("semantics.txt","")
            ios = latest.get("ios_tree.json", {})
            latest_slim = f"Latest bundle: {json.dumps(b)[:1500]}\n\nSemantics (head):\n{_truncate(sem, 1500)}\n\niOS tree:\n{_truncate(json.dumps(ios), 1500)}"
            parts.append({"text": f"[latest_failure_bundle]\n{_truncate(latest_slim, 4000)}"})
    if use_jira: parts.append({"text": f"[jira]\n{_truncate(ctx.get('jira',''), 4000)}"})

    mdl = _gem_model(sys_prompt)
    resp = mdl.generate_content(parts)
    return resp.text.strip()

def spec_to_feature_from_jira(jira_text: str) -> str:
    ctx = load_context()
    sys_prompt = textwrap.dedent("""
    You write production-ready Gherkin .feature files for the Marriott Bonvoy mobile app.
    Constraints:
    - Reuse canonical phrases from steps.yaml only
    - Prefer Android testTag over visible text; parameterize literals (dates, cities, room types)
    - Include tags (@regression @pilot_ai @en_US by default unless specified)
    - Use Scenario Outline + Examples table when values repeat
    Return ONLY valid .feature content (no commentary).
    """).strip()
    examples = "\n\n".join(
        [f"### {Path(f['path']).name}\n{_truncate(f['text'], 2500)}" for f in ctx.get("features", [])[:3]]
    )
    parts = [
        {"text": f"[Jira]\n{_truncate(jira_text, 6000)}"},
        {"text": f"[steps.yaml]\n{_truncate(ctx.get('steps',''), 5000)}"},
        {"text": f"[style_guide.md]\n{_truncate(ctx.get('style',''), 3000)}"},
        {"text": f"[golden_features]\n{examples}"},
    ]
    mdl = _gem_model(sys_prompt)
    resp = mdl.generate_content(parts)
    return resp.text.strip()

def heal_from_bundle() -> Dict[str, Any]:
    latest = load_latest_failure_bundle()
    if not latest:
        return {"error": "No latest run found. Simulate FAIL first."}
    failing = (latest.get("bundle.json") or {}).get("failing_label", "")
    sem_txt = latest.get("semantics.txt", "")
    ios_json = latest.get("ios_tree.json", {})
    sys_prompt = textwrap.dedent("""
    You are a mobile QE healing assistant. From semantics and iOS accessibility trees,
    propose a stable cross-platform selector rebind for the failing logical key.
    Prefer Android Jetpack Compose testTag and iOS accessibilityIdentifier.
    Return strictly minified JSON with fields:
      {"android":{"testTag":"..."}, "ios":{"accessibilityId":"..."}, "confidence":0..1, "rationale":"..."}
    """).strip()
    mdl = _gem_model(sys_prompt)
    resp = mdl.generate_content([
        {"text": f"[Failing key]\n{failing}"},
        {"text": f"[Semantics.txt]\n{_truncate(sem_txt, 8000)}"},
        {"text": f"[iOS tree]\n{_truncate(json.dumps(ios_json), 6000)}"},
        {"text": "Return ONLY minified JSON."}
    ])
    txt = resp.text.strip()
    try:
        if "```" in txt:
            txt = txt.split("```")[1].strip("json").strip()
        data = json.loads(txt)
    except Exception:
        data = {
            "android": {"testTag": failing or "btn.viewPrices"},
            "ios": {"accessibilityId": failing or "btn.viewPrices"},
            "confidence": 0.55,
            "rationale": "Fallback parse; please verify selectors."
        }
    # opportunistically write proposals into catalogs (preview behavior)
    try:
        if failing:
            # Android map
            cat = load_json(SYN_CFG) or {}
            cat[failing] = {"testTag": data["android"]["testTag"]}
            SYN_CFG.write_text(json.dumps(cat, indent=2))
            # Platform parity
            pm = load_json(PLAT_MAP) or {}
            pm.setdefault(failing, {})
            pm[failing]["android"] = {"testTag": data["android"]["testTag"]}
            pm[failing]["ios"] = {"accessibilityId": data["ios"]["accessibilityId"]}
            PLAT_MAP.write_text(json.dumps(pm, indent=2))
    except Exception as e:
        data["_write_warning"] = f"Could not write catalogs: {e}"
    return {"failing": failing, **data}

def risk_matrix_from_change(change_hint: str, locales=None, devices=None) -> str:
    locales = locales or ["en_US","es_ES","de_DE","fr_FR","ar_SA"]
    devices = devices or ["Pixel 7 Pro","Samsung S22","iPhone 14","iPhone 15 Pro"]
    sys_prompt = "You are a QA planner. Build a small, prioritized device×locale matrix as Markdown."
    mdl = _gem_model(sys_prompt)
    resp = mdl.generate_content([
        {"text": f"[Change list]\n{change_hint}"},
        {"text": f"Locales available: {', '.join(locales)}"},
        {"text": f"Devices available: {', '.join(devices)}"},
        {"text": "Return Markdown table with 6–12 cells and a brief rationale."}
    ])
    return resp.text.strip()

# ---------- UI ----------
st.set_page_config(page_title="Bonvoy Self-Healing QE Demo", layout="wide")
st.title("🏨 Bonvoy Self-Healing QE Demo (Synthetic) + 🤝 Gemini 2.5 QA Copilot")
st.caption("Workflow • Metrics • Chatbot — Self-healing selectors, BDD authoring from Jira, risk matrices, and artifact Q&A")

# ----- Top Navigation (always visible; no dropdown) -----
nav = st.radio(
    "Sections",
    ["Workflow", "Vision", "Metrics", "Chatbot"],
    index=0,
    horizontal=True,
)
# ---------- Vision renderer ----------
def render_vision_section():
    st.subheader("Vision Overlays (Bonvoy Home)")

    # Ensure screenshot is in place (copies repo-root bonvoy.png → assets if needed)
    vision_ready = ensure_vision_inputs()

    # Resolve original screenshot and processed overlays
    from pathlib import Path

    def first_existing(*candidates):
        for c in candidates:
            p = Path(c)
            if p.exists():
                return p
        return None

    IMG_ASSETS = VIS_ROOT / "assets"
    IMG_OUT = VIS_OUT

    # --- Debug: show where we’re looking + let user supply/replace image ---
    selectors_json = IMG_OUT / "selectors.json"
    with st.expander("Screenshot source & quick fixes", expanded=False):
        st.write("We look for the screenshot in these paths (first hit wins):")
        probe_paths = [
            IMG_ASSETS / "bonvoy.png",
            IMG_ASSETS / "bonvoy.PNG",
            IMG_ASSETS / "bonvoy.jpeg",
            IMG_ASSETS / "bonvoy.jpg",
            REPO / "bonvoy.png",
            REPO / "bonvoy.PNG",
            REPO / "bonvoy.jpeg",
            REPO / "bonvoy.jpg",
        ]
        rows = []
        for p in probe_paths:
            rows.append({"path": str(p), "exists": Path(p).exists()})
        try:
            import pandas as _pd2
            st.dataframe(_pd2.DataFrame(rows), use_container_width=True)
        except Exception:
            st.json(rows)

        up = st.file_uploader("Upload or replace Bonvoy screenshot (png/jpg/jpeg)", type=["png","jpg","jpeg"])
        if up is not None:
            (IMG_ASSETS).mkdir(parents=True, exist_ok=True)
            target = IMG_ASSETS / "bonvoy.png"
            target.write_bytes(up.getbuffer())
            st.success(f"Saved to {target}. Reloading…")
            time.sleep(0.4)
            st.rerun()

        manual = st.text_input("Or paste a full path to an existing image to copy as assets/bonvoy.png")
        if manual:
            mp = Path(manual).expanduser().resolve()
            if mp.exists():
                (IMG_ASSETS).mkdir(parents=True, exist_ok=True)
                (IMG_ASSETS / "bonvoy.png").write_bytes(mp.read_bytes())
                st.success(f"Copied from {mp} → {IMG_ASSETS/'bonvoy.png'}. Reloading…")
                time.sleep(0.4)
                st.rerun()
            else:
                st.warning(f"Path does not exist: {mp}")

    raw_img = first_existing(
        IMG_ASSETS / "bonvoy.png",
        IMG_ASSETS / "bonvoy.PNG",
        IMG_ASSETS / "bonvoy.jpeg",
        IMG_ASSETS / "bonvoy.JPEG",
        IMG_ASSETS / "bonvoy.jpg",
        IMG_ASSETS / "bonvoy.JPG",
        REPO / "bonvoy.png",
        REPO / "bonvoy.PNG",
        REPO / "bonvoy.jpeg",
        REPO / "bonvoy.JPEG",
        REPO / "bonvoy.jpg",
        REPO / "bonvoy.JPG",
    )
    ann_img = VIS_IMG_ANN
    trunc_img = VIS_IMG_TRUNC

    # Show original + processed overlays
    c1, c2, c3 = st.columns(3)
    with c1:
        st.caption("Original screenshot")
        if raw_img and Path(raw_img).exists():
            st.image(str(raw_img), use_container_width=True)
            st.caption(str(raw_img))
        else:
            st.warning(
                "Original screenshot not found.\n\n"
                "Place it at `vision_demo/assets/bonvoy.png` (or bonvoy.jpg/.jpeg) "
                "and click **Vision: Regenerate Overlays**."
            )
    with c2:
        st.caption("Annotated ROIs & labels")
        if ann_img.exists():
            st.image(str(ann_img), use_container_width=True)
            st.caption(str(ann_img))
        else:
            st.info("No annotated overlay yet. Click **Vision: Regenerate Overlays**.")
    with c3:
        st.caption("Truncation ‘red-dot’ overlay")
        if trunc_img.exists():
            st.image(str(trunc_img), use_container_width=True)
            st.caption(str(trunc_img))
        else:
            st.info("No truncation overlay yet. Click **Vision: Regenerate Overlays**.")

    # Detected controls table (from generate_selectors.py)
    st.markdown("### Detected controls & selector proposals")
    if selectors_json.exists():
        try:
            data = json.loads(selectors_json.read_text() or "{}")
        except Exception as e:
            st.error(f"Failed to read selectors.json: {e}")
            data = {}
        controls = data.get("controls", [])
        if controls:
            import pandas as _pd
            rows = []
            for c in controls:
                proposed = (c.get("proposed") or {})
                rows.append({
                    "key": c.get("key", ""),
                    "bounds": c.get("bounds", ""),
                    "android.testTag": proposed.get("testTag", ""),
                    "ios.accessibilityIdentifier": proposed.get("accessibilityIdentifier", ""),
                    "confidence": c.get("confidence", "")
                })
            df = _pd.DataFrame(rows, columns=["key", "bounds", "android.testTag", "ios.accessibilityIdentifier", "confidence"])
            st.dataframe(df, use_container_width=True)
            # Quick search
            q = st.text_input("Find a control (e.g., cta.discover, tab.book, tab.trips)")
            if q:
                sub = df[df["key"].str.contains(q, case=False, na=False)]
                if len(sub):
                    st.markdown("**Matches**")
                    st.dataframe(sub, use_container_width=True)
                else:
                    st.info("No matches.")
        else:
            st.info("No controls in selectors.json. Re-run the vision pipeline.")
    else:
        st.info("`selectors.json` not found. Run: `python vision_demo/tools/run_visual_demo.py`")

    # One-click regenerate
    st.markdown("#### Regenerate overlays")
    if vis_btn:
        if not vision_ready:
            st.error("Bonvoy screenshot not found (expected vision_demo/assets/bonvoy.png or bonvoy.png at repo root).")
        else:
            ok1, out1 = run_tool(VIS_TOOLS / "annotate_rois.py", VIS_TOOLS)
            ok2, out2 = run_tool(VIS_TOOLS / "generate_selectors.py", VIS_TOOLS)
            ok3, out3 = run_tool(VIS_TOOLS / "truncation_probe.py", VIS_TOOLS)
            st.code(((out1 or "") + "\n" + (out2 or "") + "\n" + (out3 or "")).strip(), language="bash")
            time.sleep(0.5)
            st.rerun()

# Sidebar Actions
with st.sidebar:
    st.header("Actions")
    gen_btn = st.button("1) Generate .feature", use_container_width=True)
    fail_btn = st.button("2) Simulate FAIL (create bundle)", use_container_width=True)
    heal_btn = st.button("3) Heal Latest Failure", use_container_width=True)
    pass_btn = st.button("4) Re-run (expect PASS)", use_container_width=True)
    bs_btn   = st.button("5) Write Synthetic BrowserStack", use_container_width=True)
    qm_btn   = st.button("6) Write Synthetic QMetry", use_container_width=True)
    rep_btn  = st.button("7) Show Consolidated Report", use_container_width=True)
    st.markdown("---")
    vis_btn  = st.button("Vision: Regenerate Overlays", use_container_width=True)
    st.markdown("---")
    all_btn  = st.button("🚀 Run All (1→7)", use_container_width=True)
    st.markdown("---")

    # Gemini controls
    st.header("Gemini (optional)")
    gem_api = st.text_input("GEMINI_API_KEY", type="password", value=os.getenv("GEMINI_API_KEY", ""))
    gem_model = st.selectbox("Model", ["gemini-2.5-pro","gemini-2.0-pro-exp","gemini-1.5-pro","gemini-pro"], index=0)
    gem_timeout = st.slider("Timeout (s)", min_value=5, max_value=120, value=int(os.getenv("GEMINI_TIMEOUT_S", "25")))
    st.caption("Leave key empty to use local fallback. Timeout controls the max wait for Gemini.")
    if gem_api:
        os.environ["GEMINI_API_KEY"] = gem_api
    os.environ["GEMINI_MODEL_PRO"] = gem_model
    os.environ["GEMINI_TIMEOUT_S"] = str(gem_timeout)
    gem_gen_btn  = st.button("Gemini: Spec → Feature", use_container_width=True)
    gem_heal_btn = st.button("Gemini: Heal Latest Failure", use_container_width=True)
    gem_all      = st.button("🤖 Run All w/ Gemini", use_container_width=True)
    st.markdown("---")

    # Advanced data buttons
    st.header("Data scaling")
    synth_count = st.number_input("Bulk synthesize runs", min_value=1, max_value=2000, value=50, step=10)
    synth_go = st.button("Generate Bundles", use_container_width=True)
    use_gem_ens = st.checkbox("Use Gemini in Ensemble Heal", value=True)
    ens_batch = st.button("Batch Heal Unhealed (Ensemble)", use_container_width=True)
    collect_btn = st.button("Collect Metrics", use_container_width=True)
    st.markdown("---")

    # Optional: Open PR with selector changes (requires gh CLI)
    pr_btn = st.button("Open PR with latest selector changes (if gh configured)", use_container_width=True)

# ---------- Shared Workflow functions ----------
def do_generate():
    ok, out = run_tool(SYN_TOOLS / "generate_feature.py", SYN_TOOLS)
    st.code(out or "(no output)", language="bash")
    return ok

def do_fail():
    ok, out = run_tool(SYN_TOOLS / "simulate_run.py", SYN_TOOLS)
    st.code(out or "(no output)", language="bash")
    return ok

def do_heal():
    ok, out = run_tool(SYN_TOOLS / "heal.py", SYN_TOOLS)
    st.code(out or "(no output)", language="bash")
    return ok

def do_ensemble_heal(use_gemini: bool):
    args = ["--use-gemini"] if use_gemini else []
    ok, out = run_tool_with_args(SYN_TOOLS / "ensemble_heal.py", SYN_TOOLS, args)
    st.code(out or "(no output)", language="bash")
    return ok

def do_pass():
    ok, out = run_tool(SYN_TOOLS / "simulate_run.py", SYN_TOOLS)
    st.code(out or "(no output)", language="bash")
    return ok

def do_bs():
    ok, out = run_tool(SYN_TOOLS / "synth_browserstack.py", SYN_TOOLS)
    st.code(out or "(no output)", language="bash")
    return ok

def do_qmetry():
    ok, out = run_tool(SYN_TOOLS / "synth_qmetry.py", SYN_TOOLS)
    st.code(out or "(no output)", language="bash")
    return ok

def do_report():
    ok, out = run_tool(SYN_TOOLS / "report.py", SYN_TOOLS)
    st.code(out or "(no output)", language="bash")
    return ok

def do_gemini_feature():
    try:
        out = spec_to_feature_from_jira(read_text(JIRA_SPEC))
        st.success("Generated .feature (see below)")
        st.code(out or "(no output)", language="gherkin")
        # Save for convenience
        out_path = SYN_ROOT / "bdd" / "features" / "TC_APP_FromChat.feature"
        out_path.write_text(out)
        st.caption(f"Saved to: {out_path}")
        return True
    except Exception as e:
        st.error(f"Gemini generation failed: {e}")
        return False

def do_gemini_heal():
    try:
        res = heal_from_bundle()
        st.json(res)
        return True
    except Exception as e:
        st.error(f"Gemini heal failed: {e}")
        return False

def do_bulk_synthesize(n: int):
    ok, out = run_tool_with_args(SYN_TOOLS / "bulk_synthesize.py", SYN_TOOLS, ["--count", str(n)])
    st.code(out or "(no output)", language="bash")
    return ok

# ---------- Sections ----------
if nav == "Workflow":
    status_col1, status_col2, status_col3 = st.columns(3)
    with status_col1:
        sel = selector_status()
        st.subheader("Selector Mapping")
        st.write("`btn.viewRates` →", sel)
    with status_col2:
        lr = latest_run_folder()
        st.subheader("Latest Run")
        st.write(str(lr) if lr else "No runs yet")
    with status_col3:
        st.subheader("Paths")
        st.write("Synthetic:", str(SYN_ROOT))
        st.write("Vision:", str(VIS_ROOT))

    st.markdown("---")

    # Big buttons in main area (visible even if sidebar is collapsed)
    main1, main2 = st.columns([1,1])
    with main1:
        go_all = st.button("🚀 Run All (1→7) — main", type="primary", use_container_width=True)
    with main2:
        go_gem_all = st.button("🤖 Run All w/ Gemini — main", use_container_width=True)

    if go_all:
        do_generate(); do_fail(); do_heal(); do_pass(); do_bs(); do_qmetry(); do_report()
        st.success("Done. See artifacts under synthetic_demo/runs/<latest>.")

    if go_gem_all:
        do_fail(); do_gemini_heal(); do_pass(); do_report()
        st.success("Gemini loop complete ✅")

    render_vision_section()
    st.markdown("---")

    # ---------- Workflow controls ----------
    st.subheader("Synthetic Self-Healing Workflow")

    cols = st.columns(3)
    with cols[0]:
        if gen_btn: do_generate()
        if fail_btn: do_fail()
    with cols[1]:
        if heal_btn: do_heal()
        if pass_btn: do_pass()
    with cols[2]:
        if bs_btn: do_bs()
        if qm_btn: do_qmetry()
        if rep_btn: do_report()

    # Gemini actions (optional one-offs)
    if 'gem_gen_btn' in locals() and gem_gen_btn:
        do_gemini_feature()
    if 'gem_heal_btn' in locals() and gem_heal_btn:
        do_gemini_heal()

    # One-click Gemini loop (sidebar)
    if 'gem_all' in locals() and gem_all:
        do_fail()
        do_gemini_heal()
        do_pass()
        do_report()
        st.success("Gemini loop complete ✅")

    # Data scaling & ensemble
    if 'synth_go' in locals() and synth_go:
        do_bulk_synthesize(int(synth_count))
    if 'ens_batch' in locals() and ens_batch:
        healed = 0
        for run_dir in sorted([p for p in SYN_RUNS.glob("run_*") if p.is_dir()]):
            if not (run_dir / "heal_report.md").exists():
                ok, out = run_tool_with_args(
                    SYN_TOOLS / "ensemble_heal.py",
                    SYN_TOOLS,
                    (["--use-gemini"] if use_gem_ens else []) + ["--run", str(run_dir)]
                )
                st.code(f"[{run_dir.name}]\n" + (out or "(no output)"), language="bash")
                healed += 1 if ok else 0
        st.success(f"Batch heal complete. Healed ~{healed} runs.")

    st.markdown("---")

    # ---------- Artifacts viewer ----------
    st.subheader("Artifacts (Latest Run)")
    lr = latest_run_folder()
    if lr:
        b_path = lr / "bundle.json"
        h_path = lr / "heal_report.md"
        bs_path = lr / "browserstack_run.json"
        qm_path = lr / "qmetry_update.json"
        sem_path = lr / "semantics.txt"
        uia_path = lr / "uiauto.xml"

        col1, col2 = st.columns(2)
        with col1:
            st.caption("Failure bundle")
            st.json(load_json(b_path))
            st.caption("Semantics dump (snippet)")
            st.code(read_text(sem_path)[:1200], language="text")
        with col2:
            st.caption("Heal report")
            st.markdown(read_text(h_path) or "_(no heal report yet)_")
            st.caption("BrowserStack")
            st.json(load_json(bs_path) or {})
            st.caption("QMetry payload")
            st.json(load_json(qm_path) or {})

        # Selector diff (simple before/after illustration)
        st.subheader("Selector Diff (btn.viewRates)")
        current_map = load_json(SYN_CFG) or {}
        before = {"btn.viewRates": {"testTag": "home.tab.wishlists"}}
        after = {"btn.viewRates": current_map.get("btn.viewRates")}
        st.code(json_diff(before, after) or "(no change)", language="diff")
    else:
        st.info("No run artifacts yet. Click ‘Simulate FAIL’ to create a bundle.")

elif nav == "Vision":
    render_vision_section()

elif nav == "Metrics":
    st.subheader("Heals History & Metrics")
    hist_path = SYN_ROOT / "runs" / "history.csv"
    if collect_btn:
        ok, out = run_tool(SYN_TOOLS / "collect_metrics.py", SYN_TOOLS)
        st.code(out or "(no output)", language="bash")

    if hist_path.exists() and pd is not None:
        df = pd.read_csv(hist_path)
        st.dataframe(df, use_container_width=True)
        if not df.empty:
            st.caption("Chosen keys (top)")
            try:
                st.bar_chart(df["chosen_key"].value_counts(), use_container_width=True)
            except Exception:
                st.info("Not enough data for chosen-key chart.")
            if "confidence" in df.columns:
                try:
                    conf_series = pd.to_numeric(df["confidence"], errors="coerce").fillna(0)
                    st.caption("Confidence distribution")
                    st.bar_chart(conf_series, use_container_width=True)
                except Exception:
                    st.info("No numeric confidence values yet.")
    else:
        st.info("No history yet. Use ‘Collect Metrics’ or run the demo first.")

elif nav == "Chatbot":
    st.subheader("Gemini 2.5 QA Copilot")
    st.caption("Ask for BDD from Jira, propose Android/iOS heals, build risk matrices, or summarize artifacts.")

    # Quick actions (button bar — no dropdowns)
    st.markdown("#### Quick actions")
    if "qa_action" not in st.session_state:
        st.session_state["qa_action"] = "Just chat"

    bcols = st.columns([1.2, 2.2, 2.6, 1.6, 2.6])
    if bcols[0].button("Just chat", use_container_width=True):
        st.session_state["qa_action"] = "Just chat"
    if bcols[1].button("Spec → Feature from Jira", use_container_width=True):
        st.session_state["qa_action"] = "Spec → Feature from Jira"
    if bcols[2].button("Heal from Latest Failure Bundle", use_container_width=True):
        st.session_state["qa_action"] = "Heal from Latest Failure Bundle"
    if bcols[3].button("Risk Matrix Plan", use_container_width=True):
        st.session_state["qa_action"] = "Risk Matrix Plan"
    if bcols[4].button("Summarize BrowserStack/QMetry", use_container_width=True):
        st.session_state["qa_action"] = "Summarize BrowserStack/QMetry"

    action = st.session_state["qa_action"]
    st.caption(f"Selected: **{action}**")

    if action == "Spec → Feature from Jira":
        jira_text = st.text_area("Paste Jira text (or leave to use synthetic_demo/jira_case.md)", value=read_text(JIRA_SPEC), height=200)
        if st.button("Generate .feature via Gemini"):
            try:
                out = spec_to_feature_from_jira(jira_text)
                st.success("Generated .feature")
                st.code(out, language="gherkin")
                out_path = SYN_ROOT / "bdd" / "features" / "TC_APP_FromChat.feature"
                out_path.write_text(out)
                st.caption(f"Saved to: {out_path}")
            except Exception as e:
                st.error(f"Gemini generation failed: {e}")

    elif action == "Heal from Latest Failure Bundle":
        if st.button("Propose cross-platform heal via Gemini"):
            try:
                res = heal_from_bundle()
                st.json(res)
            except Exception as e:
                st.error(f"Gemini heal failed: {e}")

    elif action == "Risk Matrix Plan":
        change = st.text_area("Describe change list or impacted screens", value="rate-selector, trips tab, login dialog")
        if st.button("Generate risk matrix via Gemini"):
            try:
                plan = risk_matrix_from_change(change)
                st.markdown(plan)
            except Exception as e:
                st.error(f"Gemini plan failed: {e}")

    elif action == "Summarize BrowserStack/QMetry":
        latest = load_latest_failure_bundle()
        if not latest:
            st.info("No latest run to summarize. Simulate FAIL first.")
        else:
            st.markdown("### BrowserStack")
            st.json(latest.get("browserstack_run.json", {}) or {})
            st.markdown("### QMetry")
            st.json(latest.get("qmetry_update.json", {}) or {})

    else:
        # plain chat mode
        if "chat_msgs" not in st.session_state:
            st.session_state["chat_msgs"] = [
                {"role": "assistant", "content": "Hi! Paste Jira for BDD, ask for a heal proposal, or request a risk matrix."}
            ]

        for m in st.session_state["chat_msgs"]:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])

        user_msg = st.chat_input("Ask about BDD, healing, test planning, or artifacts…")
        if user_msg:
            st.session_state["chat_msgs"].append({"role": "user", "content": user_msg})
            with st.chat_message("user"):
                st.markdown(user_msg)
            with st.chat_message("assistant"):
                try:
                    answer = chat_answer(user_msg, {
                        "use_steps": True, "use_style": True, "use_feats": True,
                        "use_sel": True, "use_bundle": True, "use_jira": True
                    })
                except Exception as e:
                    answer = f"Gemini call failed: {e}\n\nTip: set GEMINI_API_KEY in the sidebar or use Quick actions."
                st.markdown(answer)
                st.session_state["chat_msgs"].append({"role": "assistant", "content": answer})

# ---------- PR Button wiring (optional) ----------
if pr_btn:
    try:
        # Make a small PR with catalog changes, if any
        branch = f"selfheal-{int(time.time())}"
        subprocess.run(["git", "checkout", "-b", branch], cwd=str(REPO))
        add_list = []
        if SYN_CFG.exists(): add_list.append(str(SYN_CFG.relative_to(REPO)))
        if PLAT_MAP.exists(): add_list.append(str(PLAT_MAP.relative_to(REPO)))
        if add_list:
            subprocess.run(["git", "add", *add_list], cwd=str(REPO))
            subprocess.run(["git", "commit", "-m", "Self-heal: selector rebinds (auto)"], cwd=str(REPO))
            # Try gh CLI if available
            gh = subprocess.run(["which", "gh"], capture_output=True, text=True)
            if gh.returncode == 0:
                subprocess.run(["gh", "pr", "create", "--fill", "--title", "Self-heal: selector rebinds", "--body", "Automated heal via Ensemble/Gemini pipeline."], cwd=str(REPO))
                st.success("Opened PR via gh CLI.")
            else:
                st.warning("gh CLI not found; committed branch locally. Push & open PR manually.")
        else:
            st.info("No selector files to add.")
    except Exception as e:
        st.error(f"PR creation failed: {e}")