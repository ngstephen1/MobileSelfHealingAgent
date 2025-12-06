<div align="center">

# Mobile App Self-healing Test Agent

_Catch regressions fast, stabilize selectors automatically, and draft BDD from Jira._

<!-- TOP BADGES -->
<img src="https://img.shields.io/badge/license-MIT-informational" alt="license">
<img src="https://img.shields.io/badge/last_commit-today-success" alt="last-commit">
<img src="https://img.shields.io/badge/app-Streamlit-ff4b4b" alt="streamlit">
<img src="https://img.shields.io/badge/coverage-bdd%20%26%20vision-blue" alt="coverage">
<img src="https://img.shields.io/badge/languages-2-1f6feb" alt="languages">

<!-- TECH BADGES -->
<br/>
<img src="https://img.shields.io/badge/iOS-000000?logo=apple&logoColor=white" alt="iOS">
<img src="https://img.shields.io/badge/Android-3DDC84?logo=android&logoColor=white" alt="Android">
<img src="https://img.shields.io/badge/Swift-F05138?logo=swift&logoColor=white" alt="Swift">
<img src="https://img.shields.io/badge/Kotlin-7F52FF?logo=kotlin&logoColor=white" alt="Kotlin">
<img src="https://img.shields.io/badge/scikit--learn-f7931e?logo=scikitlearn&logoColor=white" alt="sklearn">
<img src="https://img.shields.io/badge/NumPy-013243?logo=numpy&logoColor=white" alt="numpy">
<img src="https://img.shields.io/badge/Python-3776ab?logo=python&logoColor=white" alt="python">
<img src="https://img.shields.io/badge/pandas-150458?logo=pandas&logoColor=white" alt="pandas">
<img src="https://img.shields.io/badge/JSON-000?logo=json&logoColor=white&labelColor=000" alt="json">
<img src="https://img.shields.io/badge/Markdown-000?logo=markdown&logoColor=white&labelColor=000" alt="md">
<img src="https://img.shields.io/badge/Streamlit-ff4b4b?logo=streamlit&logoColor=white" alt="streamlit">
<img src="https://img.shields.io/badge/Jupyter-f37626?logo=jupyter&logoColor=white" alt="jupyter">

</div>

---

## ✨ What it does
- **Self-heals locators** on failure (Compose `testTag`, iOS `accessibilityIdentifier`) and writes a patch proposal.  
- **Vision checks**: annotated ROIs + truncation “red-dot” overlay from a single app screenshot.  
- **BDD acceleration**: drafts Gherkin from Jira spec using your canonical `steps.yaml`.  
- **One-click run**: Generate → Fail → Heal → Re-run → BrowserStack/QMetry summaries → Report.

## 🚀 Quick start
```bash
# 1) Create venv and install
python -m venv .venv && source .venv/bin/activate
pip install -r ui_demo/requirements.txt

# 2) (Optional) set LLM key
export GEMINI_API_KEY=YOUR_KEY

# 3) Run the UI
python -m streamlit run ui_demo/streamlit_app.py --server.port 8510
