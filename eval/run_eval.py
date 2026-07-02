"""
eval/run_eval.py - Evaluation harness for the AIOps Incident Response Assistant

Drives the REAL production path (agents.ROUTER -> specialist agent -> RAG chain,
including app.py's misroute-fallback rule) over the query set in
test_queries.py and reports:

  * routing accuracy (overall and per domain)
  * retrieval hit rate (did the right runbook chunks come back?)
  * fallback rate (empty-retrieval handoff to the General agent)
  * latency per stage (route / answer) and per domain

Outputs: eval/results.json (per-query records) and eval/summary.md, plus a
console table.

Free-tier reality (learned the hard way): this key allows only 20
gemini-2.5-flash requests **per day**, and one query costs 2 (route + answer).
The harness therefore:
  * paces queries (--delay, default 15s) and retries transient 429s with the
    same escalating waits ingest.py uses;
  * detects DAILY-quota exhaustion (retrying is pointless), saves everything
    completed so far, and exits cleanly;
  * supports --resume: re-run the same command after the quota resets
    (midnight Pacific) and it continues from where it stopped, merging
    results across days until all queries are done.

Usage (from the repo root):
    python eval/run_eval.py             # start a run
    python eval/run_eval.py --resume    # continue an interrupted run
    python eval/run_eval.py --limit 2   # smoke test
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

# Allow `import agents` when run as `python eval/run_eval.py` from the repo root
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(REPO_ROOT, ".env"))

from agents import ROUTER, get_agent          # noqa: E402
from rag_chain import LLM_MODEL               # noqa: E402
from test_queries import QUERIES              # noqa: E402

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_PATH = os.path.join(EVAL_DIR, "results.json")
SUMMARY_PATH = os.path.join(EVAL_DIR, "summary.md")

# Same transient-429 handling as ingest.py: escalating waits, then give up.
RETRY_DELAYS = [20, 40, 60]


class DailyQuotaExhausted(Exception):
    """The free-tier *daily* request cap is spent - waiting will not help."""


def _is_rate_limit(msg):
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg


def _is_daily_quota(msg):
    # The daily cap surfaces as quotaId "GenerateRequestsPerDayPerProjectPerModel..."
    return "PerDay" in msg or "per day" in msg.lower()


def with_retry(fn, label):
    """Run fn(); retry transient 429s like ingest.py, fail fast on daily quota."""
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - classify by message, re-raise others
            msg = str(e)
            if _is_rate_limit(msg) and _is_daily_quota(msg):
                raise DailyQuotaExhausted(msg) from e
            if _is_rate_limit(msg) and attempt < len(RETRY_DELAYS):
                wait = RETRY_DELAYS[attempt]
                print(f"    rate-limited during {label}; retrying in {wait}s "
                      f"({attempt + 1}/{len(RETRY_DELAYS)})", flush=True)
                time.sleep(wait)
                continue
            raise


def source_names(sources):
    """Normalised runbook filenames for a list of retrieved documents."""
    return sorted(set(
        str(doc.metadata.get("source", "unknown")).replace("\\", "/").rsplit("/", 1)[-1]
        for doc in sources
    ))


def is_hit(case, sources):
    """Did retrieval surface relevant chunks for this case?

    - If the case names an expected runbook, a hit requires that file among
      the retrieved sources.
    - Otherwise a hit means at least one retrieved chunk carries the expected
      domain metadata (for `general`, any retrieved chunk counts).
    """
    if not sources:
        return False
    if case.get("expected_source"):
        return any(case["expected_source"] in name for name in source_names(sources))
    if case["expected_domain"] == "general":
        return True
    return any(doc.metadata.get("domain") == case["expected_domain"] for doc in sources)


def run_case(case):
    """Route + answer one query through the production path; return a record."""
    query = case["query"]

    t0 = time.perf_counter()
    agent = with_retry(lambda: ROUTER.route(query), "routing")
    route_s = time.perf_counter() - t0
    routed_domain = agent.domain

    t1 = time.perf_counter()
    result = with_retry(lambda: agent.run(query), "answering")
    sources = result.get("source_documents", [])

    # Replicate app.py's misroute fallback: empty retrieval -> General agent.
    fell_back = False
    if not sources and agent.domain != "general":
        agent = get_agent("general")
        result = with_retry(lambda: agent.run(query), "fallback answering")
        sources = result.get("source_documents", [])
        fell_back = True
    answer_s = time.perf_counter() - t1

    return {
        "id": case["id"],
        "query": query,
        "expected_domain": case["expected_domain"],
        "routed_domain": routed_domain,
        "routing_correct": routed_domain == case["expected_domain"],
        "retrieval_hit": is_hit(case, sources),
        "fell_back": fell_back,
        "answering_domain": agent.domain,
        "sources": source_names(sources),
        "route_latency_s": round(route_s, 2),
        "answer_latency_s": round(answer_s, 2),
        "total_latency_s": round(route_s + answer_s, 2),
        "answer_preview": str(result.get("result", ""))[:300],
    }


def summarise(records, total_planned):
    """Aggregate records into overall + per-domain metrics."""
    domains = []
    for r in records:
        if r["expected_domain"] not in domains:
            domains.append(r["expected_domain"])

    def pct(part, whole):
        return round(100.0 * part / whole, 1) if whole else 0.0

    per_domain = {}
    for d in domains:
        rs = [r for r in records if r["expected_domain"] == d]
        per_domain[d] = {
            "n": len(rs),
            "routing_accuracy_pct": pct(sum(r["routing_correct"] for r in rs), len(rs)),
            "retrieval_hit_pct": pct(sum(r["retrieval_hit"] for r in rs), len(rs)),
            "avg_route_latency_s": round(sum(r["route_latency_s"] for r in rs) / len(rs), 2),
            "avg_answer_latency_s": round(sum(r["answer_latency_s"] for r in rs) / len(rs), 2),
            "avg_total_latency_s": round(sum(r["total_latency_s"] for r in rs) / len(rs), 2),
        }

    n = len(records)
    return {
        "n_queries_completed": n,
        "n_queries_planned": total_planned,
        "complete": n == total_planned,
        "routing_accuracy_pct": pct(sum(r["routing_correct"] for r in records), n),
        "retrieval_hit_pct": pct(sum(r["retrieval_hit"] for r in records), n),
        "fallback_count": sum(r["fell_back"] for r in records),
        "fallback_rate_pct": pct(sum(r["fell_back"] for r in records), n),
        "avg_total_latency_s": round(sum(r["total_latency_s"] for r in records) / n, 2) if n else 0,
        "per_domain": per_domain,
    }


def write_summary_md(summary, records, runs):
    """Render summary.md with the headline metrics and per-domain table."""
    misroutes = [r for r in records if not r["routing_correct"]]
    status = ("COMPLETE" if summary["complete"]
              else f"PARTIAL — {summary['n_queries_completed']}/{summary['n_queries_planned']} "
                   "queries (free-tier daily quota); run `python eval/run_eval.py --resume` "
                   "after the quota resets to finish")
    lines = [
        "# Evaluation Summary",
        "",
        f"- **Status:** {status}",
        f"- **Run(s):** {'; '.join(runs)} (UTC) — production path "
        "(route → specialist → domain-filtered retrieval → answer)",
        f"- **Model:** {LLM_MODEL} (routing + answering), Gemini free tier",
        f"- **Routing accuracy:** {summary['routing_accuracy_pct']}% "
        f"({summary['n_queries_completed'] - len(misroutes)}/{summary['n_queries_completed']})",
        f"- **Retrieval hit rate:** {summary['retrieval_hit_pct']}% "
        "(expected runbook among retrieved sources)",
        f"- **Empty-retrieval fallback rate:** {summary['fallback_rate_pct']}% "
        f"({summary['fallback_count']} of {summary['n_queries_completed']})",
        f"- **Avg end-to-end latency:** {summary['avg_total_latency_s']}s per query "
        "(free-tier API round trips; no local GPU)",
        "",
        "| Expected domain | n | Routing acc. | Retrieval hits | Avg route (s) | Avg answer (s) | Avg total (s) |",
        "|---|---|---|---|---|---|---|",
    ]
    for d, m in summary["per_domain"].items():
        lines.append(
            f"| {d} | {m['n']} | {m['routing_accuracy_pct']}% | {m['retrieval_hit_pct']}% "
            f"| {m['avg_route_latency_s']} | {m['avg_answer_latency_s']} | {m['avg_total_latency_s']} |"
        )

    lines += ["", "## Misrouted queries", ""]
    if misroutes:
        for r in misroutes:
            lines.append(f"- `{r['id']}` expected **{r['expected_domain']}**, "
                         f"routed **{r['routed_domain']}**: \"{r['query']}\"")
    else:
        lines.append("None.")

    lines += [
        "",
        "## Notes on fallback semantics",
        "",
        "Ambiguous/off-domain queries are handled by the **router** classifying them",
        "`general` directly — that is the designed path, and it is measured by the",
        "`general` rows above. The separate *empty-retrieval* fallback (specialist",
        "returns zero chunks → General agent retries) is a safety net that can only",
        "fire when a routed domain has no documents; with every domain populated,",
        "a fallback rate of 0% is the expected healthy result.",
        "",
    ]
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def load_previous():
    """Load records + run timestamps from a previous (partial) run, if any."""
    if not os.path.exists(RESULTS_PATH):
        return [], []
    with open(RESULTS_PATH, encoding="utf-8") as f:
        payload = json.load(f)
    return payload.get("results", []), payload.get("meta", {}).get("runs", [])


def save(records, runs, delay, total_planned):
    """Write results.json + summary.md from the merged record set."""
    order = {c["id"]: i for i, c in enumerate(QUERIES)}
    records = sorted(records, key=lambda r: order.get(r["id"], 999))
    summary = summarise(records, total_planned)
    payload = {
        "meta": {
            "runs": runs,
            "llm_model": LLM_MODEL,
            "n_queries_completed": len(records),
            "n_queries_planned": total_planned,
            "delay_between_queries_s": delay,
        },
        "summary": summary,
        "results": records,
    }
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    write_summary_md(summary, records, runs)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Run the routing/retrieval evaluation.")
    parser.add_argument("--delay", type=float, default=15.0,
                        help="seconds to wait between queries (free-tier pacing, default 15)")
    parser.add_argument("--limit", type=int, default=None,
                        help="only run the first N queries (smoke test)")
    parser.add_argument("--resume", action="store_true",
                        help="continue a previous run, skipping completed queries")
    args = parser.parse_args()

    if not os.getenv("GOOGLE_API_KEY"):
        print("ERROR: GOOGLE_API_KEY is not set. Copy .env.example to .env first.")
        sys.exit(1)
    if not os.path.isdir(os.path.join(REPO_ROOT, "chroma_db")):
        print("ERROR: chroma_db/ not found. Run `python ingest.py` first.")
        sys.exit(1)

    planned = QUERIES[: args.limit] if args.limit else QUERIES
    records, runs = ([], []) if not args.resume else load_previous()
    done_ids = {r["id"] for r in records}
    todo = [c for c in planned if c["id"] not in done_ids]
    runs = runs + [datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")]

    if not todo:
        print("Nothing to do - all planned queries already have results.")
        save(records, runs[:-1], args.delay, len(planned))
        return

    print(f"Running {len(todo)} of {len(planned)} queries "
          f"({len(done_ids)} already done, delay {args.delay}s)\n", flush=True)

    quota_hit = False
    for i, case in enumerate(todo, 1):
        print(f"[{i:>2}/{len(todo)}] {case['id']}: {case['query'][:70]}", flush=True)
        try:
            record = run_case(case)
        except DailyQuotaExhausted:
            quota_hit = True
            print("\n*** Free-tier DAILY quota for the chat model is exhausted. ***",
                  flush=True)
            break
        records.append(record)
        status = "OK " if record["routing_correct"] else "MISROUTE"
        hit = "hit" if record["retrieval_hit"] else "MISS"
        fb = " +fallback" if record["fell_back"] else ""
        print(f"        -> {record['routed_domain']} [{status}] retrieval {hit}{fb} "
              f"({record['total_latency_s']}s)", flush=True)
        if i < len(todo):
            time.sleep(args.delay)

    summary = save(records, runs, args.delay, len(planned))

    print("\n" + "=" * 62)
    label = "COMPLETE" if summary["complete"] else "PARTIAL"
    print(f"Status           : {label} "
          f"({summary['n_queries_completed']}/{summary['n_queries_planned']} queries)")
    if summary["n_queries_completed"]:
        print(f"Routing accuracy : {summary['routing_accuracy_pct']}%")
        print(f"Retrieval hits   : {summary['retrieval_hit_pct']}%")
        print(f"Fallback rate    : {summary['fallback_rate_pct']}% "
              f"({summary['fallback_count']} queries)")
        print(f"Avg latency      : {summary['avg_total_latency_s']}s per query")
        print("=" * 62)
        print(f"{'domain':<16}{'n':>3}{'route acc':>11}{'hits':>7}{'avg total s':>13}")
        for d, m in summary["per_domain"].items():
            print(f"{d:<16}{m['n']:>3}{m['routing_accuracy_pct']:>10}%"
                  f"{m['retrieval_hit_pct']:>6}%{m['avg_total_latency_s']:>13}")
    print(f"\nWrote {RESULTS_PATH}\nWrote {SUMMARY_PATH}")
    if quota_hit:
        print("\nThe free-tier daily cap (20 gemini-2.5-flash requests/day on this key)")
        print("resets at midnight Pacific. Continue with:")
        print("    python eval/run_eval.py --resume")


if __name__ == "__main__":
    main()
