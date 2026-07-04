# Kaggle Writeup — paste each field into the competition's "New Writeup" form

> Fill the two placeholders before submitting:
> `[YOUTUBE-LINK]` — your demo video, and `[LIVE-APP-URL]` — your Streamlit
> Cloud URL (or delete that line if you don't want to link the live app).

---

## Field: Title

AIOps Incident Response Assistant — a multi-agent on-call copilot

## Field: Subtitle

A router agent orchestrates six specialized AI agents to deliver contextual, step-by-step incident response guidance from your team's runbooks — reducing MTTR when every minute matters.

## Field: Project Description

*(~1,350 words — the form allows 2,500)*

---

### The problem: the fix exists, but nobody can find it at 3 a.m.

When production breaks, the clock starts. The remediation steps for most incidents already exist — written into a runbook after the last time it happened. But those runbooks live scattered across wikis, shared drives, and PDFs, organized by whoever wrote them and searchable only by exact keywords. An on-call engineer paged at 3 a.m. about `OOMKilled` pods doesn't need a generic chatbot's best guess; they need *their team's* procedure — the exact `kubectl` commands, the cluster's memory-limit conventions, the escalation path, and when to roll back. Every minute spent hunting for that document is added directly to the Mean Time To Recovery.

**AIOps Incident Response Assistant** turns a folder of plain-text and PDF runbooks into a team of AI agents that answers incident questions with numbered, actionable remediation steps — grounded in, and cited back to, the team's own documentation.

### Why a multi-agent system, not just another RAG chatbot

The naive solution is a single RAG chatbot over all documents. That was the first version of this project — and it retrieves noise, because incident vocabulary overlaps brutally across domains. "Memory" appears in Kubernetes OOM runbooks *and* database buffer-pool runbooks. "Connection" spans networking, databases, and TLS certificates. "Timeout" is everywhere. A single vector store cheerfully returns Kubernetes chunks for a database question, and the LLM then blends two unrelated runbooks into remediation steps that nobody actually wrote.

The fix is the same one real incident response uses: specialization. Organizations don't page one generalist for everything — they have a network engineer, a DBA, a security responder. This project mirrors that structure as a **router + specialists** multi-agent pattern:

- **🧭 Router Agent** — classifies each incoming query into exactly one domain (`kubernetes`, `database`, `infrastructure`, `network`, `security`, or `general`) with a single temperature-0 Gemini call. Its output parsing is defensive: exact label match first, then substring tolerance, then a safe default to `general` — a malformed LLM response can never crash routing.
- **Six specialist agents** — ☸️ Kubernetes, 🗄️ Database, 🖥️ Infrastructure, 🌐 Network, 🔒 Security, and 🚀 CI/CD. Each is a retrieval-augmented chain whose ChromaDB retriever is *hard-filtered* by domain metadata, so a specialist can only ever see — and only ever cite — its own runbooks. Cross-domain contamination is eliminated at the retrieval layer, not papered over in the prompt.
- **🧭 General Agent** — an unfiltered fallback that searches the entire knowledge base, used when a query fits no specialty.

```
Engineer query
      │
      ▼
🧭 Router (Gemini, temperature 0)
      │ classifies into one domain
      ├── kubernetes ──► ☸️  Kubernetes Agent ─┐
      ├── database ────► 🗄️  Database Agent ───┤   domain-filtered
      ├── infrastructure► 🖥️  Infra Agent ─────┼─► ChromaDB retrieval ─► Gemini answer
      ├── network ─────► 🌐  Network Agent ────┤
      ├── security ────► 🔒  Security Agent ───┤
      ├── cicd ────────► 🚀  CI/CD Agent ──────┘
      └── general ─────► 🧭  General Agent ──────► unfiltered retrieval
                                                          │
                                                          ▼
                                    answer + routing trace + cited sources
```

Two properties make this trustworthy enough for an incident context:

**Self-correction.** If a routed specialist comes back with zero source documents, the app automatically retries with the General Agent across all runbooks — a wrong routing decision can never hide the right runbook. The UI tells the engineer this handoff happened.

**Honesty and observability.** Every answer displays the Router → Specialist handoff as a colored agent badge, and lists the exact runbook files the answer was drawn from. When nothing in the knowledge base matches, the assistant is instructed to open with *"I don't have a specific runbook for this, but here is general guidance:"* rather than inventing a source. In incident response, a confident wrong answer is worse than no answer — the engineer can always verify where guidance came from before trusting it.

### How it works end to end

**Ingestion** (`ingest.py`): the pipeline walks `data/runbooks/<domain>/`, where each subfolder name *is* the domain — a convention that keeps the router's labels, the retrieval filters, and the folder structure in sync by construction. Documents are chunked (1,000 characters, 200 overlap), embedded with Gemini's `gemini-embedding-2`, and persisted to a local ChromaDB store with each chunk tagged with its domain. The pipeline is idempotent (it deletes the old store before rebuilding, so re-runs never duplicate), retries transient 429 rate limits with escalating backoff, and even tolerates Windows/OneDrive file-lock quirks — real-world friction that tutorial code ignores.

**Query time**: a routed question costs two Gemini calls — one to classify, one to answer from the top-3 domain-filtered chunks. The answering prompt enforces incident-appropriate output: numbered steps, rollback and escalation guidance when relevant, and a calm, professional tone. The Streamlit chat UI renders the routing trace, the answer, and the source citations.

**The agent registry** (`agents.py`): specialists are declared as frozen dataclasses in a single registry — name, domain, role, goal, badge color. Chains are built lazily and cached per domain. Adding a new domain to the team is a new runbook subfolder plus one entry in a list; the metadata filtering and routing pick it up automatically.

### Engineering decisions worth noting

- **Metadata filtering over separate collections.** One vector store with a `domain` filter (rather than six collections) keeps ingestion single-pass and lets the General Agent search everything for free.
- **Single-constant model configuration.** Gemini model names get retired regularly; the chat model and embedding model are each defined exactly once and imported everywhere else. The embedding constant is shared between ingestion and query — the class of silent corruption where the two sides embed with different models is impossible by construction.
- **Free-tier engineering.** The whole system runs on Gemini's free tier: call budgeting (2 calls per query), 429-aware retries during ingestion, and a friendly rate-limit message in the UI instead of a stack trace.
- **Deployment realism.** The app is deployed on Streamlit Cloud. The repo ships the prebuilt vector store so a fresh deploy answers from the first request, and pins the `protobuf`/`opentelemetry` transitive dependencies that otherwise crash ChromaDB on Streamlit Cloud — a bug found and fixed the hard way.

### Measured, not just claimed

The repo ships a reproducible evaluation harness (`python eval/run_eval.py`)
that drives the real production path — router → specialist → domain-filtered
retrieval → answer, including the fallback rule — over 20 labelled queries
across all domains plus deliberately ambiguous cases. Interim results
(**[UPDATE-WITH-FINAL-NUMBERS from eval/summary.md before submitting]**):
**11/11 routing accuracy (100%)** and **11/11 retrieval hits (100%)** across
the kubernetes, database, infrastructure, and network domains, 10.46s average
end-to-end latency on free-tier API round trips. The harness paces itself and
resumes across days to respect the free tier's 20-requests/day cap — quota
discipline as a first-class design constraint.

**Extensibility was tested, not asserted:** adding a brand-new CI/CD specialist
(3 runbooks) took under 10 minutes and changed only data plus two registry
entries (~8 lines) — zero core-logic changes. Domain-filtered retrieval
returned exclusively `cicd` chunks with the correct runbook as the top source
for all three probe queries (full report: `eval/extensibility_test.md`).

### How it was vibe-coded

In the spirit of this course, the project was built conversationally with an AI coding agent (Claude Code). The architecture discussions, the multi-agent registry, the Windows file-lock handling, the free-tier retry logic, code reviews that caught documentation drift, and the Streamlit Cloud deployment fixes were all produced through iterative AI pair-work: describe the intent, review the agent's plan, let it implement, verify in the running app. A `CLAUDE.md` file in the repo acts as the coding agent's persistent project memory — capturing hard-won rules (embedding/store compatibility, process-wide chain caching, LangChain 1.x import paths) so every new session starts already knowing the project's sharp edges. The repo's commit history is itself an artifact of the vibe-coding workflow.

### Tech stack

| Component     | Tool                      |
|---------------|---------------------------|
| LLM           | Google Gemini 2.5 Flash   |
| Embeddings    | Google gemini-embedding-2 |
| Orchestration | LangChain 1.x             |
| Vector store  | ChromaDB (local)          |
| UI            | Streamlit                 |

### Try it

- 🚀 **Live demo:** [LIVE-APP-URL]
- 💻 **Code:** https://github.com/sarveshkb21/aiops-incident-response-assistant
- ▶️ **Video:** [YOUTUBE-LINK]

Run locally: clone, `pip install -r requirements.txt`, add a free Gemini API key to `.env`, and `streamlit run app.py`. The repo ships a prebuilt vector store and sample runbooks across all six domains, so it works out of the box; `python ingest.py` rebuilds the knowledge base from your own runbooks, and `python eval/run_eval.py` reproduces the evaluation below.

### Limitations and what's next

- **No conversational memory** — each query is independent, so follow-up questions don't see prior turns. Next step: LCEL `create_retrieval_chain` with chat history.
- **Single-label routing** — a cross-domain incident (a network failure cascading into database timeouts) routes to one specialist. The natural evolution is multi-domain fan-out with answer synthesis across specialists.
- **Relevance thresholds** — retrieval currently returns the nearest chunks regardless of similarity score; a threshold would let specialists decline weak matches and trigger the General fallback more often.
- **From advice to diagnosis** — the most exciting next step is giving specialists read-only diagnostic tools (`kubectl describe`, SQL `EXPLAIN`, `ping`/`traceroute`) so agents can inspect live system state, not just recall documentation.
