# Evaluation Summary

- **Status:** COMPLETE
- **Note:** 7 record(s) reconstructed from the console log of an earlier run that crashed on a network error before saving (routing/hit/latency values exact as logged; per-stage latency split and source lists were not captured).
- **Run(s):** 2026-07-02 07:47:52; 2026-07-04 14:16:00; 2026-07-04 14:23:52; 2026-07-04 14:27:42; 2026-07-05 13:12:26 (UTC) — production path (route → specialist → domain-filtered retrieval → answer)
- **Model:** gemini-2.5-flash (routing + answering), Gemini free tier
- **Routing accuracy:** 100.0% (20/20)
- **Retrieval hit rate:** 100.0% (expected runbook among retrieved sources)
- **Empty-retrieval fallback rate:** 0.0% (0 of 20)
- **Avg end-to-end latency:** 10.81s per query (free-tier API round trips; no local GPU)

| Expected domain | n | Routing acc. | Retrieval hits | Avg route (s) | Avg answer (s) | Avg total (s) |
|---|---|---|---|---|---|---|
| kubernetes | 2 | 100.0% | 100.0% | 2.24 | 9.12 | 11.37 |
| database | 3 | 100.0% | 100.0% | None | None | 11.3 |
| infrastructure | 3 | 100.0% | 100.0% | None | None | 10.56 |
| network | 3 | 100.0% | 100.0% | 2.42 | 6.66 | 8.93 |
| security | 3 | 100.0% | 100.0% | 2.46 | 10.36 | 12.82 |
| cicd | 3 | 100.0% | 100.0% | 2.54 | 6.79 | 9.33 |
| general | 3 | 100.0% | 100.0% | 2.11 | 9.46 | 11.57 |

## Misrouted queries

None.

## Notes on fallback semantics

Ambiguous/off-domain queries are handled by the **router** classifying them
`general` directly — that is the designed path, and it is measured by the
`general` rows above. The separate *empty-retrieval* fallback (specialist
returns zero chunks → General agent retries) is a safety net that can only
fire when a routed domain has no documents; with every domain populated,
a fallback rate of 0% is the expected healthy result.
