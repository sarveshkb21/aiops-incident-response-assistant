# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

AIOps Incident Response Assistant — a RAG chatbot that answers IT on-call
questions from local runbooks. Stack: **Streamlit** UI → **LangChain 1.x** →
**ChromaDB** (local vector store) → **Google Gemini** (LLM + embeddings).

## Architecture (5 files)

- `ingest.py` — one-off pipeline: recursively loads `data/runbooks/**/*.{txt,pdf}`,
  tags each doc with `domain` metadata (its subfolder name), chunks, embeds with
  Gemini, and persists to `./chroma_db`. Auto-deletes `chroma_db/` before rebuild
  (so re-running never duplicates) and retries on transient 429s. Run before the
  app and after adding/changing runbooks.
- `router.py` — `classify_query(query) -> str`: one Gemini call that classifies a
  query into a domain (`kubernetes`, `database`, `infrastructure`, `network`,
  `security`, `general`). Owns the `DOMAINS` list. Robust parsing falls back to
  `general`.
- `rag_chain.py` — builds RetrievalQA chains (Chroma retriever + Gemini LLM). Owns
  shared constants `CHROMA_DIR` and `EMBEDDING_MODEL`. Two builders:
  `get_rag_chain()` (unfiltered, kept for compatibility) and
  `get_agent_chain(domain)` (filters the retriever by `domain` metadata; `general`
  = no filter).
- `agents.py` — multi-agent registry (pure LangChain, no CrewAI): an `Agent`
  dataclass (name/domain/role/goal/emoji/colour + `.run()`), the `AGENTS` dict of
  5 specialists + `general`, and a `ROUTER` that wraps `classify_query`. Chains are
  cached per domain via `lru_cache`. This is the layer `app.py` drives.
- `app.py` — Streamlit chat UI. Per query: `ROUTER.route()` → `agent.run()` →
  Router→Specialist routing trace above the answer. Misroute fallback: if a
  specialist returns no sources, it hands off to the `general` agent.

Data flow: `ingest.py` writes `chroma_db/` (with `domain` metadata) → `router.py`
picks the domain → `rag_chain.get_agent_chain(domain)` reads the filtered store →
`app.py` serves queries. Note: a routed query makes 2 Gemini calls (route +
answer), or 3 if the fallback fires — relevant on the free tier.

## Run commands (Windows / PowerShell, venv at `.\venv`)

```powershell
.\venv\Scripts\activate
pip install -r requirements.txt
python ingest.py            # build the vector store (run first)
streamlit run app.py        # launch UI at http://localhost:8501
```

## Critical project rules (learned the hard way)

1. **Embedding model must match between ingest and query.** It is defined once as
   `EMBEDDING_MODEL` in `rag_chain.py` and imported by `ingest.py`. If you change
   it, you MUST delete `chroma_db/` and re-run `python ingest.py` — old and new
   embeddings have incompatible dimensions.

2. **Gemini model names get retired.** A `404 NOT_FOUND` means the model is gone;
   a `429 RESOURCE_EXHAUSTED` with `limit: 0` means it's paid-tier only (e.g.
   `gemini-2.5-pro` is not on the free tier — use `gemini-2.5-flash`). To list
   what's currently available on the key:
   ```python
   from google import genai; import os
   c = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
   for m in c.models.list(): print(m.name, m.supported_actions)
   ```

3. **Fully restart Streamlit after editing `rag_chain.py` or `agents.py`.** The
   domain chains are cached process-wide via `@lru_cache` on `agents._chain_for`
   (NOT `@st.cache_resource`), so the app's ⋮ menu → Clear cache does NOT
   invalidate them. Only a Ctrl+C restart rebuilds the chains.

4. **LangChain 1.x import paths.** This project is on LangChain 1.x:
   - `RetrievalQA` → `from langchain_classic.chains import RetrievalQA`
   - `PromptTemplate` → `from langchain_core.prompts import PromptTemplate`
   - `Chroma` → `from langchain_chroma import Chroma` (NOT `langchain_community`)
   - text splitters → `from langchain_text_splitters import ...`

## Conventions

- Secrets live in `.env` (`GOOGLE_API_KEY`), never committed. Both entry points
  guard for a missing key with a clear message.
- Runbooks are plain `.txt`/`.pdf` under `data/runbooks/<domain>/`. The subfolder
  name becomes the doc's `domain` metadata, which `get_agent_chain` filters on and
  `router.py` routes to. Adding a runbook to an *existing* domain needs no code
  changes (just re-ingest). Adding a *new* domain also requires adding it to
  `DOMAINS` in `router.py` (and ideally the router prompt + `DOMAIN_STYLES` badge
  map in `app.py`).
- The router/specialist domains, the `data/runbooks/` subfolders, and the `domain`
  metadata must all stay in sync, or routing silently misses (the misroute
  fallback in `app.py` then searches everything as a safety net).

## Known tech debt (works, but dated)

- `RetrievalQA` is deprecated (runs via the `langchain-classic` compat layer). The
  modern path is LCEL + `create_retrieval_chain`.
- No conversational memory — each query is independent; follow-up questions don't
  see prior turns.
