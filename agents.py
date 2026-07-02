"""
agents.py - Multi-Agent Registry (pure LangChain + Gemini, no CrewAI)

Defines the incident-response "team":

  * ROUTER         - classifies an incoming query into a domain (router.py).
  * 6 specialists  - Kubernetes, Database, Infrastructure, Network, Security,
                     CI/CD. Each answers ONLY from its own runbooks via
                     get_agent_chain(<domain>) (rag_chain.py).
  * General agent  - fallback that searches all runbooks (no domain filter).

This is a "router + specialists" multi-agent pattern: one Gemini call routes,
then a domain specialist answers. The specialists are domain-scoped RAG chains,
not autonomous tool-using agents.
"""

from dataclasses import dataclass
from functools import lru_cache

from rag_chain import get_agent_chain
from router import classify_query


@dataclass(frozen=True)
class Agent:
    """A domain specialist that answers from its own runbooks."""

    name: str
    domain: str
    role: str
    goal: str
    emoji: str
    color: str

    def run(self, query: str) -> dict:
        """Answer `query` from this agent's domain runbooks.

        Returns the RetrievalQA result dict (keys: 'result', 'source_documents').
        """
        return _chain_for(self.domain).invoke({"query": query})


@lru_cache(maxsize=None)
def _chain_for(domain: str):
    """Build (once per domain, process-wide) the domain-scoped RAG chain."""
    return get_agent_chain(domain)


# The specialist team. Domains match router.DOMAINS and the runbook subfolders.
AGENTS = {
    "kubernetes": Agent(
        name="Kubernetes Agent", domain="kubernetes",
        role="Kubernetes & container-platform specialist",
        goal="Resolve pod, deployment, and cluster incidents from the kubernetes runbooks.",
        emoji="☸️", color="#326CE5",
    ),
    "database": Agent(
        name="Database Agent", domain="database",
        role="Database reliability specialist",
        goal="Resolve connection, replication, and query incidents from the database runbooks.",
        emoji="🗄️", color="#2E7D32",
    ),
    "infrastructure": Agent(
        name="Infrastructure Agent", domain="infrastructure",
        role="Host & compute specialist",
        goal="Resolve CPU, memory, disk, and service-health incidents from the infrastructure runbooks.",
        emoji="🖥️", color="#F57C00",
    ),
    "network": Agent(
        name="Network Agent", domain="network",
        role="Network & connectivity specialist",
        goal="Resolve DNS, latency, and connectivity incidents from the network runbooks.",
        emoji="🌐", color="#6A1B9A",
    ),
    "security": Agent(
        name="Security Agent", domain="security",
        role="Security incident responder",
        goal="Contain and resolve access, TLS, and intrusion incidents from the security runbooks.",
        emoji="🔒", color="#C62828",
    ),
    "cicd": Agent(
        name="CI/CD Agent", domain="cicd",
        role="CI/CD & release-pipeline specialist",
        goal="Resolve pipeline, build, and release incidents from the cicd runbooks.",
        emoji="🚀", color="#00838F",
    ),
    "general": Agent(
        name="General Agent", domain="general",
        role="Generalist / fallback responder",
        goal="Answer using all runbooks when no single domain clearly applies.",
        emoji="🧭", color="#546E7A",
    ),
}


def get_agent(domain: str) -> Agent:
    """Look up an agent by domain, defaulting to the General agent."""
    return AGENTS.get(domain, AGENTS["general"])


class Router:
    """Classifies a query and dispatches it to the right specialist agent."""

    name = "Router"
    emoji = "🧭"

    def route(self, query: str) -> Agent:
        """Return the specialist Agent that should handle `query`."""
        return get_agent(classify_query(query))


ROUTER = Router()
