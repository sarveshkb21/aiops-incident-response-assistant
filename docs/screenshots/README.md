# Demo Screenshots — Capture Guide

Three annotated screenshots that evidence the writeup's claims. Save them in
this folder with the exact filenames below, then embed them in the Kaggle
writeup (the writeup editor supports image upload) and/or the repo README.

## Automated capture (recommended)

`capture.py` does all of this unattended — starts the app headlessly, runs
the three queries, screenshots each full conversation (annotations placed
from the live DOM), and records a `.webm` screen demo to `docs/video/`
(YouTube accepts `.webm` directly; add a voiceover using VIDEO_SCRIPT.md).

```powershell
.\venv\Scripts\python.exe -m pip install playwright
.\venv\Scripts\python.exe -m playwright install chromium
.\venv\Scripts\python.exe docs\screenshots\capture.py        # 3 queries = 6 Gemini calls
```

Mind the free tier: a full run costs 6 of the 20 daily requests.

## Manual capture — Setup

```powershell
.\venv\Scripts\activate
streamlit run app.py
```

Use a clean browser window (no bookmarks bar, ~1280px wide). On Windows,
capture with **Win+Shift+S** (rectangular snip). Annotate afterwards with any
editor (even Paint) — a red rounded rectangle + short label is enough.

Free-tier note: each query costs 2 Gemini calls. Space the three captures
~30s apart and you will never see a 429.

## 1. `01_routed_query_with_sources.png` — specialist routing + attribution

- Query: `How do I resolve OOMKilled pods in Kubernetes?` (sidebar button works)
- Wait for the full answer.
- Capture the whole chat area including the sidebar.
- **Annotate:**
  - the routing trace line `🧭 Router → ☸️ Kubernetes Agent` — label it
    *"Router hands off to the domain specialist"*
  - the `Sources: runbook_oom_kubernetes.txt` line at the bottom — label it
    *"Answer cited to the team's own runbook"*

## 2. `02_general_agent_honesty.png` — off-domain query, honest answer

- Query: `Our office printer says PC LOAD LETTER, what now?`
- **Annotate:**
  - the badge `🧭 Router → 🧭 General Agent` — label it
    *"No specialist fits → General agent searches all runbooks"*
  - the answer opening *"I don't have a specific runbook for this, but here
    is general guidance:"* — label it
    *"Admits the gap instead of inventing a source"*

## 3. `03_new_domain_cicd.png` — extensibility evidence

- Query: `GitHub Actions pipeline stuck in queued for two hours, blocking a hotfix`
- **Annotate:**
  - the badge `🧭 Router → 🚀 CI/CD Agent` — label it
    *"Domain added in <10 min — registry entry only, no core-logic changes"*
  - the `Sources: runbook_pipeline_stuck.txt` line — label it
    *"Retrieves from the newly ingested runbooks"*

## Checklist

- [ ] All three PNGs saved in `docs/screenshots/` with the names above
- [ ] Text readable at 100% zoom (don't downscale below ~1200px width)
- [ ] No personal info visible (browser profile icon, other tabs)
- [ ] Committed to the repo so the README/writeup can reference them
