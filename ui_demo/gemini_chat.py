# ui_demo/gemini_chat.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🤝 QA Copilot (Android + iOS) — Company-grade chat with EVIDENCE
- Grounded answers with inline evidence pulled from your repo (features, configs, artifacts, and optional source code)
- Handles general + technical questions; politely flags out-of-scope but can still assist with a disclaimer
- Intent routing (BDD / Heal / Risk / Artifacts / Search / Explain)
- Evidence pinboard, filename + content search, and "require citations" guardrail
- External links (QMetry, BrowserStack, Docs) shown contextually
- Horizontal quick action bar (no dropdowns)
- NEW: Slash commands (/bdd, /heal, /risk, /artifacts, /explain, /search, /help)
- NEW: Attach extra context files (Jira text, .feature, .json, .md) and search them too
- NEW: Export last answer or full chat (with evidence) as Markdown
"""
from __future__ import annotations

import os, sys, json, difflib, re, datetime, hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import streamlit as st

# ---------- Repo bootstrap ----------
REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

# ---------- Local tools (LLM wrappers + context helpers) ----------
from llm.gemini_tools import (
    load_context, latest_run_folder, load_latest_failure_bundle,
    chat_answer, spec_to_feature_from_jira, heal_from_bundle, risk_matrix_from_change
)

# ---------- Page ----------
st.set_page_config(page_title="QE Copilot (Android + iOS)", layout="wide")
st.title("🤝 QE Copilot (Android + iOS)")
st.caption("Draft BDD • Propose selector heals • Plan risk matrices • Summarize artifacts • Explain files — with **grounded evidence** and actionable links.")

# ---------- Sidebar ----------
with st.sidebar:
    st.header("Gemini")
    api = st.text_input("GEMINI_API_KEY", type="password", value=os.getenv("GEMINI_API_KEY",""))
    model = st.selectbox("Model", ["gemini-2.5-pro","gemini-2.0-pro-exp","gemini-1.5-pro","gemini-pro"], index=0)
    os.environ["GEMINI_MODEL_PRO"] = model
    if api:
        os.environ["GEMINI_API_KEY"] = api

    st.divider()
    st.header("Context controls")
    use_steps  = st.checkbox("Include steps.yaml", True)
    use_style  = st.checkbox("Include style guide", True)
    use_feats  = st.checkbox("Include golden features", True)
    use_sel    = st.checkbox("Include selector catalogs", True)
    use_bundle = st.checkbox("Include latest failure bundle", True)
    use_jira   = st.checkbox("Include jira_case.md", True)
    use_code   = st.checkbox("Include source code (if present)", True)

    st.divider()
    st.header("Guardrails")
    strict_mode       = st.checkbox("Strict grounding (project data only)", True)
    assist_ooo        = st.checkbox("Assist out-of-scope (with disclaimer)", True)
    attach_ev         = st.checkbox("Attach evidence under answers", True)
    require_citations = st.checkbox("Require evidence for answers", False)
    depth = st.select_slider("Answer depth", options=["brief","standard","deep"], value="standard")

    st.divider()
    st.header("External Links")
    qmetry_url = st.text_input("QMetry", os.getenv("QMETRY_URL","https://qmetry.example/"))
    bs_url     = st.text_input("BrowserStack", os.getenv("BROWSERSTACK_URL","https://browserstack.example/"))
    docs_url   = st.text_input("Docs/Wiki", os.getenv("DOCS_WIKI_URL","https://confluence.example/"))
    figma_url  = st.text_input("Figma", os.getenv("FIGMA_URL","https://figma.example/"))

# ---------- External link helper ----------
def _links_for(intent: str) -> List[str]:
    items = []
    if intent in ("artifacts","heal","risk","bdd","explain","search","generic"):
        if qmetry_url:   items.append(f"[QMetry]({qmetry_url})")
        if bs_url:       items.append(f"[BrowserStack]({bs_url})")
        if docs_url:     items.append(f"[Team Docs]({docs_url})")
    if intent in ("vision","bdd","heal"):
        if figma_url:    items.append(f"[Figma]({figma_url})")
    return items

# ---------- Load shared context once (graceful fallback) ----------
try:
    CTX = load_context()
    if not isinstance(CTX, dict):
        CTX = {}
except Exception as e:
    st.warning(f"Context load warning: {e}")
    CTX = {}

# ---------- Small helpers ----------
def path_link(p: Path, label: Optional[str] = None) -> str:
    try:
        if not isinstance(p, Path): p = Path(p)
        return f"[{label or p.name}]({str(p)})"
    except Exception:
        return label or str(p)

def _code_block(title: str, text: str, lang: str = "text"):
    st.markdown(f"**{title}**")
    st.code(text, language=lang)

def _json_block(obj: Any, title: str):
    st.markdown(f"**{title}**")
    try:
        st.json(obj)
    except Exception:
        try:
            st.code(json.dumps(obj, indent=2), language="json")
        except Exception:
            st.write(obj)

def _diff(before: Dict[str, Any], after: Dict[str, Any], title: str):
    a = json.dumps(before, indent=2).splitlines(keepends=False)
    b = json.dumps(after, indent=2).splitlines(keepends=False)
    diff = "\n".join(difflib.unified_diff(a, b, fromfile="before", tofile="after", lineterm=""))
    _code_block(title, diff or "(no change)", "diff")

def _scope_badge(text: str, kind: str = "relevant"):
    color = "#16a34a" if kind == "relevant" else "#ca8a04" if kind == "assisted" else "#ef4444"
    st.markdown(f"<span style='background:{color};color:white;padding:3px 8px;border-radius:6px;font-size:12px'>{text}</span>", unsafe_allow_html=True)

# ---------- Compatibility wrappers ----------
def _spec_to_feature_compat(jira_text: str, steps: str, style: str, feats: List[Dict[str, Any]]) -> str:
    try:
        return spec_to_feature_from_jira(jira_text, steps, style, feats)
    except TypeError:
        return spec_to_feature_from_jira(jira_text)

def _heal_compat(failing: str, sem_txt: str, ios_json: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return heal_from_bundle(failing, sem_txt, ios_json)
    except TypeError:
        return heal_from_bundle()

def _chat_answer_compat(msg: str, ctx: Dict[str, Any]) -> str:
    try:
        return chat_answer(msg, ctx)
    except TypeError:
        return chat_answer(msg)

# ---------- File system anchors ----------
SYN_ROOT   = REPO / "synthetic_demo"
SYN_RUNS   = SYN_ROOT / "runs"
BDD_DIR    = SYN_ROOT / "bdd"
FEATURES   = BDD_DIR / "features"
STEPS_YAML = BDD_DIR / "steps.yaml"
STYLE_MD   = BDD_DIR / "style_guide.md"
SEL_CAT    = SYN_ROOT / "config" / "selector_catalog.json"
PLAT_MAP   = SYN_ROOT / "config" / "platform_map.json"
JIRA_MD    = SYN_ROOT / "jira_case.md"
VIS_ROOT   = REPO / "vision_demo"
VIS_OUT    = VIS_ROOT / "outputs"
OUTPUTS    = REPO / "ui_demo" / "outputs"
OUTPUTS.mkdir(parents=True, exist_ok=True)

# Optional source roots (if present)
SRC_ROOTS: List[Path] = []
for guess in [REPO/"app", REPO/"androidApp", REPO/"iosApp", REPO/"frontend", REPO/"backend"]:
    if guess.exists():
        SRC_ROOTS.append(guess)

# ---------- Intent routing ----------
INTENTS = {
    "bdd": ["bdd","gherkin","feature file","scenario","step","steps","cucumber"],
    "heal": ["heal","locator","rebind","testtag","accessibilityidentifier","selector","self-heal","self heal"],
    "risk": ["risk","matrix","device","locale","coverage plan","prioritize","priority"],
    "artifacts": ["browserstack","qmetry","bundle","report","artifact","failure","logs","video"],
    "vision": ["screenshot","visual","truncation","red-dot","overlay","compose"],
    "search": ["where","defined","find","locate","path","file","source","selector_catalog","platform_map","steps.yaml"],
    "explain": ["explain","how does","why does","walk me through","read this file","what does this do"]
}

def classify_intent(msg: str) -> str:
    m = (msg or "").lower()
    for intent, keys in INTENTS.items():
        if any(k in m for k in keys):
            return intent
    return "generic"

def out_of_scope(msg: str) -> bool:
    m = (msg or "").lower()
    core = ["bonvoy","marriott","android","ios","qa","qe","appium","espresso","cucumber","bdd","gherkin","selector","testtag","browserstack","qmetry","compose"]
    return classify_intent(m) == "generic" and not any(k in m for k in core)

# ---------- Evidence retrieval ----------
FILE_GLOBS = ["*.feature","*.md","*.json","*.xml","*.txt","*.kt","*.java","*.swift"]

@st.cache_data(show_spinner=False, ttl=60)
def _list_candidate_files(include_code: bool) -> List[Path]:
    paths: List[Path] = []
    for p in [FEATURES, STEPS_YAML, STYLE_MD, SEL_CAT, PLAT_MAP, JIRA_MD, VIS_OUT]:
        if isinstance(p, Path) and p.exists():
            if p.is_dir():
                for g in FILE_GLOBS:
                    paths.extend(p.rglob(g))
            else:
                paths.append(p)
    run_dir = latest_run_folder()
    if run_dir and run_dir.exists():
        for g in FILE_GLOBS:
            paths.extend(run_dir.glob(g))
        paths.extend([run_dir / "bundle.json", run_dir / "browserstack_run.json", run_dir / "qmetry_update.json",
                      run_dir / "semantics.txt", run_dir / "uiauto.xml"])
    if include_code:
        for root in SRC_ROOTS:
            for g in FILE_GLOBS:
                paths.extend(root.rglob(g))
    uniq = []
    seen = set()
    for p in paths:
        try:
            rp = p.resolve()
            if rp not in seen and rp.exists() and rp.is_file():
                uniq.append(rp); seen.add(rp)
        except Exception:
            continue
    return uniq[:2000]

def _tokenize(q: str) -> List[str]:
    q = (q or "").lower()
    q = re.sub(r"[^a-z0-9_./-]+", " ", q)
    toks = [t for t in q.split() if t]
    return toks[:20]

def _score_line(line: str, toks: List[str]) -> int:
    s = 0
    L = line.lower()
    for t in toks:
        if t in L:
            s += 1
    return s

def _fname_fuzzy(base: str, q: str, toks: List[str]) -> int:
    score = 0
    base_l = base.lower()
    for t in toks:
        if t in base_l:
            score = max(score, 3)
    if q == base_l:
        score = max(score, 5)
    ratio = difflib.SequenceMatcher(None, base_l, q).ratio()
    if ratio > 0.6:
        score = max(score, int(6 * ratio))  # up to ~6
    return score

@st.cache_data(show_spinner=False, ttl=30)
def evidence_search(query: str, include_code: bool, k: int = 6) -> List[Dict[str, Any]]:
    """
    Filename + content search with short snippets (on-disk files only).
    """
    toks = _tokenize(query)
    if not toks:
        return []
    q_lower = (query or "").lower().strip()
    results: List[Dict[str, Any]] = []

    for fp in _list_candidate_files(include_code):
        try:
            text = fp.read_text(errors="ignore"); lines = text.splitlines()
        except Exception:
            continue

        base = fp.name
        fname_score = _fname_fuzzy(base, q_lower, toks)

        best, best_ln = 0, -1
        for ln, line in enumerate(lines, start=1):
            sc = _score_line(line, toks)
            if sc > best:
                best, best_ln = sc, ln

        final = max(best, fname_score)
        if final > 0:
            if best_ln > 0:
                lo = max(1, best_ln - 3); hi = min(len(lines), best_ln + 3)
                snippet = "\n".join(f"{i:>4}: {lines[i-1]}" for i in range(lo, hi+1))
                line_no = best_ln
            else:
                header = lines[:12] if lines else []
                snippet = "\n".join(f"{i+1:>4}: {header[i]}" for i in range(len(header)))
                line_no = 1
            results.append({"path":str(fp), "line":line_no, "score":final, "snippet":snippet})
    results.sort(key=lambda x: (-x["score"], x["path"]))
    return results[:k]

# ---------- Uploaded context (session-scoped) ----------
def _uploaded_ctx_key() -> str:
    files = st.session_state.get("uploaded_files", [])
    h = hashlib.md5()
    for f in files:
        h.update(f.get("name","").encode())
        h.update(str(len(f.get("text",""))).encode())
    return h.hexdigest()

def _search_uploaded(query: str, k: int = 6) -> List[Dict[str, Any]]:
    toks = _tokenize(query)
    if not toks:
        return []
    results: List[Dict[str, Any]] = []
    for f in st.session_state.get("uploaded_files", []):
        name = f.get("name","uploaded.txt")
        text = f.get("text","")
        lines = text.splitlines()
        base = name
        fname_score = _fname_fuzzy(base, (query or "").lower().strip(), toks)
        best, best_ln = 0, -1
        for ln, line in enumerate(lines, start=1):
            sc = _score_line(line, toks)
            if sc > best:
                best, best_ln = sc, ln
        final = max(best, fname_score)
        if final > 0:
            if best_ln > 0:
                lo = max(1, best_ln - 3); hi = min(len(lines), best_ln + 3)
                snippet = "\n".join(f"{i:>4}: {lines[i-1]}" for i in range(lo, hi+1))
                line_no = best_ln
            else:
                header = lines[:12] if lines else []
                snippet = "\n".join(f"{i+1:>4}: {header[i]}" for i in range(len(header)))
                line_no = 1
            results.append({"path":f"uploaded://{name}", "line":line_no, "score":final, "snippet":snippet})
    results.sort(key=lambda x: (-x["score"], x["path"]))
    return results[:k]

def search_all_evidence(query: str, include_code: bool, k: int = 6) -> List[Dict[str, Any]]:
    """Merge on-disk search and uploaded content search."""
    disk = evidence_search(query, include_code, k*2)
    up   = _search_uploaded(query, k*2)
    allr = disk + up
    # de-duplicate by (path,line)
    uniq: Dict[Tuple[str,int], Dict[str,Any]] = {}
    for r in allr:
        uniq[(r["path"], r["line"])] = r
    out = list(uniq.values())
    out.sort(key=lambda x: (-x["score"], x["path"]))
    return out[:k]

def render_evidence(evs: List[Dict[str, Any]], title: str = "Evidence from repo", allow_pin: bool = True):
    if not evs:
        st.info("No direct evidence found in repo or uploaded context for this query.")
        return
    st.markdown(f"### {title}")
    if "pinned_evidence" not in st.session_state:
        st.session_state["pinned_evidence"] = []
    for idx, e in enumerate(evs):
        st.markdown(f"- {path_link(Path(e['path'])) if not str(e['path']).startswith('uploaded://') else e['path']} : line {e['line']} (score {e['score']})")
        st.code(e["snippet"], language="text")
        if allow_pin:
            pin_key = f"pin_{e['path']}_{e['line']}_{idx}"
            if st.checkbox("Pin this evidence", key=pin_key):
                item = {"path":e["path"], "line":e["line"], "snippet":e["snippet"]}
                if item not in st.session_state["pinned_evidence"]:
                    st.session_state["pinned_evidence"].append(item)
    if st.session_state["pinned_evidence"]:
        with st.expander("📌 View pinned evidence"):
            for pe in st.session_state["pinned_evidence"]:
                p = pe['path']
                display = path_link(Path(p)) if not str(p).startswith("uploaded://") else p
                st.markdown(f"- {display} : line {pe['line']}")
                st.code(pe["snippet"], language="text")
            if st.button("Clear pinned evidence"):
                st.session_state["pinned_evidence"] = []

# ---------- Context slicer ----------
def _slim_context() -> Dict[str, Any]:
    c: Dict[str, Any] = {}
    if use_steps:  c["steps"]   = CTX.get("steps","")
    if use_style:  c["style"]   = CTX.get("style","")
    if use_feats:  c["features"]= CTX.get("features",[])
    if use_sel:
        c["selector_catalog"] = CTX.get("selector_catalog",{})
        c["platform_map"]     = CTX.get("platform_map",{})
    if use_jira:   c["jira"]    = CTX.get("jira","")
    if use_bundle: c["_bundle"] = True
    # Pinned + uploaded evidence included for stronger grounding
    pins = st.session_state.get("pinned_evidence", [])
    if pins:
        c.setdefault("evidence", [])
        c["evidence"].extend([f"{e['path']} @ {e['line']}\n{e['snippet']}" for e in pins])
    upfiles = st.session_state.get("uploaded_files", [])
    if upfiles:
        c["uploaded"] = [{"name":u["name"], "text":u["text"][:5000]} for u in upfiles]  # cap
    c["_strict"] = strict_mode
    c["_depth"]  = depth
    return c

# ---------- Quick actions ----------
st.markdown("#### Quick actions")
if "quick_action" not in st.session_state:
    st.session_state["quick_action"] = "Just chat"

qcols = st.columns([1.1, 2.1, 2.3, 1.9, 2.5, 2.2])
if qcols[0].button("Just chat", use_container_width=True):
    st.session_state["quick_action"] = "Just chat"
if qcols[1].button("Spec → Feature from Jira", use_container_width=True):
    st.session_state["quick_action"] = "Spec → Feature from Jira"
if qcols[2].button("Heal from Latest Failure Bundle", use_container_width=True):
    st.session_state["quick_action"] = "Heal from Latest Failure Bundle"
if qcols[3].button("Risk Matrix Plan", use_container_width=True):
    st.session_state["quick_action"] = "Risk Matrix Plan"
if qcols[4].button("Summarize BrowserStack/QMetry", use_container_width=True):
    st.session_state["quick_action"] = "Summarize BrowserStack/QMetry"
if qcols[5].button("Explain Code / File", use_container_width=True):
    st.session_state["quick_action"] = "Explain Code / File"

quick = st.session_state["quick_action"]
st.caption(f"Selected: **{quick}**")

# ---------- Attach extra context ----------
with st.expander("📎 Attach extra context (Jira, .feature, .json, .md)"):
    files = st.file_uploader("Upload files to include in this session's context", accept_multiple_files=True, type=["txt","md","feature","json"])
    if files:
        st.session_state.setdefault("uploaded_files", [])
        for f in files:
            try:
                text = f.read().decode("utf-8", errors="ignore")
            except Exception:
                text = ""
            st.session_state["uploaded_files"].append({"name":f.name, "text":text})
        st.success(f"Added {len(files)} file(s) to session context.")
    # Show currently attached
    cur = st.session_state.get("uploaded_files", [])
    if cur:
        st.markdown("**Attached this session:**")
        for it in cur:
            st.markdown(f"- {it['name']} ({len(it['text'])} chars)")
        if st.button("Clear attached files"):
            st.session_state["uploaded_files"] = []
            st.experimental_rerun()

# ---------- Resource helpers ----------
def show_where_to_go(intent: str, extras: Optional[List[Path]] = None):
    st.markdown("#### Where to go next")
    links: List[str] = []
    if intent == "bdd":
        links += [
            path_link(STEPS_YAML, "steps.yaml (canonical)"),
            path_link(STYLE_MD, "style_guide.md"),
            path_link(FEATURES, "features/ (save or review)"),
        ]
    if intent == "heal":
        links += [
            path_link(SEL_CAT, "selector_catalog.json (Android testTag)"),
            path_link(PLAT_MAP, "platform_map.json (Android/iOS mapping)"),
            path_link(SYN_RUNS, "runs/ (latest bundle & heal report)"),
        ]
    if intent in ("artifacts","vision","generic"):
        run_dir = latest_run_folder()
        if run_dir:
            links += [
                path_link(run_dir / "bundle.json", "latest bundle.json"),
                path_link(run_dir / "browserstack_run.json", "browserstack_run.json"),
                path_link(run_dir / "qmetry_update.json", "qmetry_update.json"),
                path_link(run_dir / "semantics.txt", "semantics.txt"),
                path_link(run_dir / "uiauto.xml", "uiauto.xml"),
            ]
        links += [
            path_link(VIS_OUT / "bonvoy_annotated.png", "Vision: annotated.png"),
            path_link(VIS_OUT / "bonvoy_truncation_overlay.png", "Vision: truncation_overlay.png"),
        ]
    if extras:
        links += [path_link(p) for p in extras if p]
    # External links
    ext = _links_for(intent or "generic")
    if ext:
        links += ext
    links += [path_link(JIRA_MD, "jira_case.md")]
    st.markdown("\n".join([f"- {x}" for x in links if x]))

# ---------- Quick actions content ----------
if quick == "Spec → Feature from Jira":
    st.subheader("Spec → Feature")
    jira_text = st.text_area("Paste Jira text (or leave to use synthetic_demo/jira_case.md)", value=CTX.get("jira",""), height=220)
    if st.button("Generate .feature"):
        steps = CTX.get("steps",""); style = CTX.get("style",""); feats = CTX.get("features",[])
        try:
            out = _spec_to_feature_compat(jira_text, steps, style, feats)
            _scope_badge("relevant"); _code_block("Generated .feature", out, "gherkin")
            out_path = REPO / "synthetic_demo" / "bdd" / "features" / "TC_APP_FromChat.feature"
            out_path.write_text(out)
            st.caption(f"Saved to: {path_link(out_path, str(out_path))}")
            st.session_state["last_answer"] = out
            st.session_state["last_evidence"] = search_all_evidence("canonical step phrases", include_code=False)
            if attach_ev:
                render_evidence(st.session_state["last_evidence"], "Evidence (steps/style)")
            show_where_to_go("bdd", [out_path])
            st.success("Feature generated and saved. Review, then commit.")
        except Exception as e:
            st.error(f"Generation failed: {e}")

elif quick == "Heal from Latest Failure Bundle":
    st.subheader("Heal Proposal (Android + iOS)")
    bundle = load_latest_failure_bundle()
    if not bundle:
        st.info("No latest run found. Use the main app to Simulate FAIL first.")
    else:
        failing = bundle.get("bundle.json",{}).get("failing_label","")
        sem_txt = bundle.get("semantics.txt","")
        ios_json = bundle.get("ios_tree.json", {})
        st.write(f"Failing key: `{failing}`")
        if st.button("Propose Heal"):
            try:
                res = _heal_compat(failing, sem_txt, ios_json)
                _scope_badge("relevant"); _json_block(res, "Cross-platform proposal")
                try:
                    before = json.loads(SEL_CAT.read_text()) if SEL_CAT.exists() else {}
                except Exception:
                    before = {}
                after = json.loads(json.dumps(before))
                if failing and isinstance(res, dict) and "android" in res and isinstance(res["android"], dict) and "testTag" in res["android"]:
                    after.setdefault(failing, {}); after[failing]["testTag"] = res["android"]["testTag"]
                _diff(before, after, "selector_catalog.json (preview diff)")
                evs = search_all_evidence(failing, include_code=use_code)
                st.session_state["last_answer"] = json.dumps(res, indent=2)
                st.session_state["last_evidence"] = evs
                if attach_ev and failing:
                    render_evidence(evs, "Evidence (catalog/features/bundle)")
                show_where_to_go("heal")
                st.success("Apply the suggested mapping, re-run, then open PR.")
            except Exception as e:
                st.error(f"Heal failed: {e}")

elif quick == "Risk Matrix Plan":
    st.subheader("Risk-based Device × Locale Matrix")
    change = st.text_area("Describe change list / impacted screens", value="booking: rate-selector, trips tab, login dialog", height=120)
    if st.button("Generate Matrix"):
        try:
            plan = risk_matrix_from_change(change)
            _scope_badge("relevant"); st.markdown(plan)
            evs = search_all_evidence(change, include_code=use_code)
            st.session_state["last_answer"] = plan
            st.session_state["last_evidence"] = evs
            if attach_ev:
                render_evidence(evs, "Evidence (related files)")
            show_where_to_go("artifacts")
            st.success("Target high-risk cells first; expand on failure.")
        except Exception as e:
            st.error(f"Matrix build failed: {e}")

elif quick == "Summarize BrowserStack/QMetry":
    st.subheader("Synthetic BrowserStack / QMetry Summary")
    bundle = load_latest_failure_bundle()
    if not bundle:
        st.info("No latest run found.")
    else:
        _scope_badge("relevant")
        bsj = bundle.get("browserstack_run.json", {}) or {}
        qmj = bundle.get("qmetry_update.json", {}) or {}
        st.markdown("### BrowserStack"); _json_block(bsj, "browserstack_run.json")
        st.markdown("### QMetry"); _json_block(qmj, "qmetry_update.json")
        evs = []
        run_dir = latest_run_folder()
        if attach_ev and run_dir:
            for name in ["browserstack_run.json","qmetry_update.json","bundle.json"]:
                fp = run_dir / name
                if fp.exists():
                    evs.append({"path":str(fp), "line":1, "score":1, "snippet": fp.read_text(errors="ignore")[:800]})
            render_evidence(evs, "Evidence (latest run payloads)", allow_pin=False)
        st.session_state["last_answer"] = json.dumps({"browserstack":bsj, "qmetry":qmj}, indent=2)
        st.session_state["last_evidence"] = evs
        show_where_to_go("artifacts")
        st.success("Attach these to your ticket; align status with QMetry.")

elif quick == "Explain Code / File":
    st.subheader("Explain Code / File")
    query = st.text_input("Type a file name, selector key, or term (e.g., btn.viewRates, platform_map.json, RateCard.kt)")
    if st.button("Explain"):
        evs = search_all_evidence(query, include_code=use_code, k=6)
        if not evs:
            st.info("No direct matches found. Try a more specific term or enable source code scanning in the sidebar.")
        else:
            _scope_badge("relevant")
            render_evidence(evs, "Evidence")
            ctx = _slim_context()
            ctx["evidence"] = [f"{e['path']} @ {e['line']}\n{e['snippet']}" for e in evs]
            try:
                instr = [
                    "Explain the above evidence (paths + snippets) for a tester.",
                    "Mention key selectors, tags, or functions.",
                    f"Answer depth: {depth}."
                ]
                ans = _chat_answer_compat("\n".join(instr), ctx)
                st.markdown(ans); show_where_to_go("explain")
                st.session_state["last_answer"] = ans
                st.session_state["last_evidence"] = evs
            except Exception as e:
                st.error(f"Gemini explanation failed: {e}")

# ---------- Evidence & Links Helper ----------
with st.expander("🔎 Evidence & Links helper"):
    q = st.text_input("Find evidence (filename or content)")
    if st.button("Search evidence"):
        evs = search_all_evidence(q, include_code=use_code, k=10)
        render_evidence(evs, "Evidence search results")
    st.caption("Pinned evidence will be included in chat context automatically.")

# ---------- Export helpers ----------
def _export_markdown(text: str, evidence: List[Dict[str,Any]], name_prefix: str) -> Optional[Path]:
    if not text:
        return None
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    fn = OUTPUTS / f"{name_prefix}_{ts}.md"
    lines = [f"# QA Copilot Export — {ts}", "", "## Answer", "", text, ""]
    if evidence:
        lines += ["## Evidence", ""]
        for e in evidence:
            lines.append(f"- {e['path']} : line {e['line']} (score {e['score']})")
            lines.append("")
            lines.append("```")
            lines.append(e["snippet"])
            lines.append("```")
            lines.append("")
    fn.write_text("\n".join(lines))
    return fn

with st.expander("💾 Export"):
    colA, colB = st.columns(2)
    if colA.button("Save LAST answer as Markdown"):
        p = _export_markdown(st.session_state.get("last_answer",""), st.session_state.get("last_evidence", []), "last_answer")
        if p:
            st.success(f"Saved: {path_link(p, str(p))}")
        else:
            st.info("No last answer available.")
    if colB.button("Save FULL chat transcript"):
        # Build transcript as markdown
        msgs = st.session_state.get("messages", [])
        text = []
        for m in msgs:
            text.append(f"**{m['role']}**\n\n{m['content']}\n")
        p = _export_markdown("\n".join(text), st.session_state.get("pinned_evidence", []), "chat_transcript")
        if p:
            st.success(f"Saved: {path_link(p, str(p))}")

# ---------- Slash commands ----------
def handle_slash(cmd: str) -> Optional[str]:
    low = cmd.strip()
    if low.startswith("/help"):
        return ("**Slash commands**\n"
                "- `/bdd <jira text>` — generate .feature\n"
                "- `/heal` — heal from latest failure bundle\n"
                "- `/risk <change list>` — risk matrix plan\n"
                "- `/artifacts` — summarize BrowserStack and QMetry\n"
                "- `/explain <term>` — explain code/file with evidence\n"
                "- `/search <term>` — find files and snippets\n")
    if low.startswith("/bdd"):
        jira = cmd[len("/bdd"):].strip() or CTX.get("jira","")
        out = _spec_to_feature_compat(jira, CTX.get("steps",""), CTX.get("style",""), CTX.get("features",[]))
        out_path = REPO / "synthetic_demo" / "bdd" / "features" / "TC_APP_FromChat.feature"
        out_path.write_text(out)
        st.session_state["last_answer"] = out
        st.session_state["last_evidence"] = search_all_evidence("canonical step phrases", include_code=False)
        return f"Generated feature saved to: {out_path}"
    if low.startswith("/heal"):
        bundle = load_latest_failure_bundle()
        if not bundle:
            return "No latest run found. Simulate FAIL first."
        failing = bundle.get("bundle.json",{}).get("failing_label","")
        sem_txt = bundle.get("semantics.txt","")
        ios_json = bundle.get("ios_tree.json", {})
        res = _heal_compat(failing, sem_txt, ios_json)
        st.session_state["last_answer"] = json.dumps(res, indent=2)
        st.session_state["last_evidence"] = search_all_evidence(failing, include_code=True)
        return f"Heal proposed for `{failing}` — see evidence below."
    if low.startswith("/risk"):
        change = cmd[len("/risk"):].strip() or "booking: rate-selector, trips tab, login dialog"
        plan = risk_matrix_from_change(change)
        st.session_state["last_answer"] = plan
        st.session_state["last_evidence"] = search_all_evidence(change, include_code=True)
        return "Risk matrix generated."
    if low.startswith("/artifacts"):
        return "Showing latest BrowserStack/QMetry artifacts below."
    if low.startswith("/explain"):
        term = cmd[len("/explain"):].strip()
        evs = search_all_evidence(term, include_code=True, k=6)
        st.session_state["last_answer"] = f"(see explanation and evidence below for: {term})"
        st.session_state["last_evidence"] = evs
        return f"Explaining `{term}` with evidence below."
    if low.startswith("/search"):
        term = cmd[len("/search"):].strip()
        evs = search_all_evidence(term, include_code=True, k=8)
        st.session_state["last_answer"] = f"(search results for: {term})"
        st.session_state["last_evidence"] = evs
        return f"Found {len(evs)} matches."
    return None

# ---------- Plain chat with intent routing ----------
if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {"role":"assistant","content":"Hi! Ask me to draft BDD from Jira, suggest a selector heal, build a risk matrix, summarize BrowserStack/QMetry, search files, or explain code. I provide grounded answers with evidence. Type `/help` for commands."}
    ]

if quick == "Just chat":
    st.subheader("Chat")
    for m in st.session_state["messages"]:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    user_msg = st.chat_input("Ask about BDD, healing, risk planning, artifacts, search, or explain <file/term> … (use /help for commands)")
    if user_msg:
        st.session_state["messages"].append({"role":"user","content":user_msg})
        with st.chat_message("user"): st.markdown(user_msg)

        # Slash commands first
        if user_msg.strip().startswith("/"):
            result = handle_slash(user_msg)
            with st.chat_message("assistant"):
                if result:
                    _scope_badge("relevant")
                    st.markdown(result)
                    # Render artifacts for certain commands
                    if user_msg.startswith("/artifacts"):
                        bundle = load_latest_failure_bundle()
                        if bundle:
                            st.markdown("### BrowserStack"); _json_block(bundle.get("browserstack_run.json", {}) or {}, "browserstack_run.json")
                            st.markdown("### QMetry"); _json_block(bundle.get("qmetry_update.json", {}) or {}, "qmetry_update.json")
                    if st.session_state.get("last_evidence"):
                        render_evidence(st.session_state["last_evidence"], "Evidence")
                    show_where_to_go("generic")
                    st.session_state["messages"].append({"role":"assistant","content":result})
            st.stop()

        # Intent routing
        intent = classify_intent(user_msg)
        scope = "relevant" if not out_of_scope(user_msg) else "out-of-scope"

        with st.chat_message("assistant"):
            evs = search_all_evidence(user_msg, include_code=use_code, k=6)
            if require_citations and not evs and not st.session_state.get("pinned_evidence"):
                _scope_badge("out-of-scope", "error")
                st.markdown("I don’t have evidence in this repo for that. Try the **Evidence & Links helper** to search and pin relevant snippets, or provide a Jira excerpt.")
                st.stop()

            ctx = _slim_context()
            if evs:
                ctx.setdefault("evidence", [])
                ctx["evidence"].extend([f"{e['path']} @ {e['line']}\n{e['snippet']}" for e in evs])

            preface = []
            if scope == "out-of-scope":
                if not assist_ooo:
                    _scope_badge("out-of-scope", "error")
                    st.markdown("This looks **out of scope** for the Bonvoy QE copilot. Supported topics: BDD, selectors & heals, risk planning, artifacts, file search/explain.")
                    st.stop()
                preface.append("Out of scope for this QA copilot; provide a short helpful answer with a disclaimer and no speculation.")
            else:
                preface.append("Ground your answer in repo evidence when available.")
            preface.append(f"Answer depth: {depth}. End with a single 'Next steps' bullet.")
            try:
                answer = _chat_answer_compat("\n".join(preface) + "\n\n" + user_msg, ctx)
                _scope_badge("assisted" if scope == "out-of-scope" else "relevant",
                             "assisted" if scope == "out-of-scope" else "relevant")
                st.markdown(answer)
                if attach_ev: render_evidence(evs, "Evidence from repo")
                show_where_to_go(intent or "generic")
                st.session_state["messages"].append({"role":"assistant","content":answer})
                st.session_state["last_answer"] = answer
                st.session_state["last_evidence"] = evs
            except Exception as e:
                st.error(f"Gemini call failed: {e}")
                st.session_state["messages"].append({"role":"assistant","content":f"(Gemini failed: {e})"})

# ---------- Footer ----------
st.caption(f"Built for Marriott QE")