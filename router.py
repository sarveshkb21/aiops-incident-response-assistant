"""
router.py - Query Domain Router
Classifies an incident query into one runbook domain using Gemini, so the
right domain-scoped chain can be selected (see `get_agent_chain` in
rag_chain.py). The domains match the subfolders under data/runbooks/.
"""

import os
from functools import lru_cache

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from rag_chain import LLM_MODEL

load_dotenv()

# Valid domains — must match the runbook subfolders and the `domain` metadata
# written by ingest.py. "general" is the catch-all / no-filter fallback.
DOMAINS = ["kubernetes", "database", "infrastructure", "network", "security", "general"]

ROUTER_PROMPT = """You are a router for an IT incident-response assistant.
Classify the engineer's query into exactly ONE of these domains:

- kubernetes: pods, containers, OOMKilled, deployments, kubectl, k8s nodes
- database: SQL, connection pools, replication, queries, deadlocks, DB outages
- infrastructure: CPU, memory, disk space, servers/VMs, host resources, service health
- network: DNS, latency, packet loss, connectivity, load balancers, firewalls
- security: unauthorized access, breaches, suspicious logins, TLS/cert issues, vulnerabilities
- general: anything that does not clearly fit one of the categories above

Respond with ONLY the domain label in lowercase. No punctuation, no explanation.

Query: {query}
Domain:"""


@lru_cache(maxsize=1)
def _router_llm() -> ChatGoogleGenerativeAI:
    """Build the classification LLM once per process."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "GOOGLE_API_KEY is not set. Copy .env.example to .env and add your "
            "Gemini API key (get one at https://aistudio.google.com/app/apikey)."
        )

    return ChatGoogleGenerativeAI(
        model=LLM_MODEL,
        google_api_key=api_key,
        temperature=0  # deterministic classification
    )


def classify_query(query: str) -> str:
    """Classify `query` into one of DOMAINS and return the label as a string.

    Falls back to "general" if the model returns anything unrecognized.
    """
    raw = _router_llm().invoke(ROUTER_PROMPT.format(query=query)).content
    label = raw.strip().lower()

    # Exact match first, then tolerate stray words/punctuation around the label.
    if label in DOMAINS:
        return label
    for domain in DOMAINS:
        if domain in label:
            return domain
    return "general"


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or "OOMKilled pods keep restarting in my cluster"
    print(f"Query:  {q}")
    print(f"Domain: {classify_query(q)}")
