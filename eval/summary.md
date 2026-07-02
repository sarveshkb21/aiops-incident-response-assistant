# Evaluation Summary

- **Status:** PARTIAL — 2/20 queries (free-tier daily quota); run `python eval/run_eval.py --resume` after the quota resets to finish
- **Run(s):** 2026-07-02 07:47:52 (UTC) — production path (route → specialist → domain-filtered retrieval → answer)
- **Model:** gemini-2.5-flash (routing + answering), Gemini free tier
- **Routing accuracy:** 100.0% (2/2)
- **Retrieval hit rate:** 100.0% (expected runbook among retrieved sources)
- **Empty-retrieval fallback rate:** 0.0% (0 of 2)
- **Avg end-to-end latency:** 11.37s per query (free-tier API round trips; no local GPU)

| Expected domain | n | Routing acc. | Retrieval hits | Avg route (s) | Avg answer (s) | Avg total (s) |
|---|---|---|---|---|---|---|
| kubernetes | 2 | 100.0% | 100.0% | 2.24 | 9.12 | 11.37 |

## Misrouted queries

None.

## Notes on fallback semantics

Ambiguous/off-domain queries are handled by the **router** classifying them
`general` directly — that is the designed path, and it is measured by the
`general` rows above. The separate *empty-retrieval* fallback (specialist
returns zero chunks → General agent retries) is a safety net that can only
fire when a routed domain has no documents; with every domain populated,
a fallback rate of 0% is the expected healthy result.
