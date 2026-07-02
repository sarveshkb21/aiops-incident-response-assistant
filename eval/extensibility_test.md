# Extensibility Test — Adding a New Domain (CI/CD)

**Claim under test:** adding a new specialist domain to the agent team requires
only *registration* (data + two list entries), with zero changes to the core
routing, retrieval, or agent-dispatch logic.

**Date:** 2026-07-02 · **Result: PASS**

## What was added

A **CI/CD** specialist (🚀 `cicd` domain) covering release/pipeline incidents —
a domain distinct from the existing six agents and common in real on-call
rotations.

## Files changed

| File | Change | Nature |
|---|---|---|
| `data/runbooks/cicd/runbook_failed_deployment.txt` | new | data (runbook) |
| `data/runbooks/cicd/runbook_pipeline_stuck.txt` | new | data (runbook) |
| `data/runbooks/cicd/runbook_artifact_registry.txt` | new | data (runbook) |
| `router.py` | +1 entry in `DOMAINS`, +1 line in the router prompt | registration |
| `agents.py` | +1 `Agent(...)` entry in the `AGENTS` registry (+docstring count) | registration |

**Core logic untouched:** `classify_query()`, `get_agent_chain()`, the
`Agent.run()` dispatch, the ingestion pipeline, and `app.py` were not modified.
The Streamlit UI picked up the new agent's badge (name, emoji, colour)
automatically from the registry entry.

## Steps and timings

| Step | Command | Time |
|---|---|---|
| Write 3 CI/CD runbooks | — | ~6 min |
| Register domain (2 files, ~8 lines) | — | ~1 min |
| Rebuild vector store | `python ingest.py` | ~1 min (43 chunks, 12 docs) |
| Verify end-to-end | `python eval/run_eval.py` (cicd-01..03) | included in eval run |

**Total: under 10 minutes** from "domain does not exist" to "specialist agent
answering routed queries in the UI", most of it spent writing runbook content.

## End-to-end verification

**Ingestion** tagged the new docs correctly:

```
Loaded 12 document(s)
  - cicd: 3 document(s)
  ...
Split into 43 chunks
SUCCESS: 43 chunks stored in ChromaDB
```

**Domain-filtered retrieval** verified directly against the store (one probe
per new runbook; every retrieved chunk carried `domain=cicd` and the correct
runbook was the top source):

```
stuck pipeline: 3 chunks, domains=['cicd'], sources=['runbook_pipeline_stuck.txt']
   bad release: 3 chunks, domains=['cicd'], sources=['runbook_failed_deployment.txt']
 registry auth: 3 chunks, domains=['cicd'], sources=['runbook_artifact_registry.txt']
```

**Routing** is exercised by the three CI/CD queries (`cicd-01`..`cicd-03`) in
the evaluation set (`eval/test_queries.py`); their results are reported in
`eval/summary.md` / `eval/results.json` alongside the original domains as the
quota-paced evaluation run completes.

## Why this works by construction

The runbook subfolder name **is** the domain: ingestion writes it into each
chunk's metadata, the router prompt lists it as a label, and the specialist's
retriever filters on it. Keeping those three in sync is a naming convention,
not code — which is what makes registration the only code change needed.
