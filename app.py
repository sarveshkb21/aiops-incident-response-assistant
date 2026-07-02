"""
app.py - AIOps Incident Response Assistant
Streamlit chat interface powered by RAG (LangChain + Gemini + ChromaDB).
Run with: streamlit run app.py
"""

import os
import warnings

# Silence non-actionable DeprecationWarnings from third-party internals
# (google-genai and chromadb warn about future Python versions, not our code).
# Must run before importing rag_chain, which triggers those imports.
warnings.filterwarnings("ignore", category=DeprecationWarning, module=r"google\.genai.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, module=r"chromadb.*")

import streamlit as st
from agents import ROUTER, get_agent
from rag_chain import CHROMA_DIR

# Page config
st.set_page_config(
    page_title="AIOps Incident Response Assistant",
    page_icon="🚨",
    layout="wide"
)

# Fail fast if the vector store has never been built — otherwise Chroma silently
# creates an empty store and every answer comes back with no sources.
if not os.path.isdir(CHROMA_DIR):
    st.error("Knowledge base not found. Run `python ingest.py` first, then restart the app.")
    st.stop()

# Header
st.title("🚨 AIOps Incident Response Assistant")
st.markdown("*Instant remediation guidance from your runbooks and KB articles*")
st.divider()

# Sidebar
with st.sidebar:
    st.header("📘 About")
    st.markdown("""
    This assistant helps on-call engineers instantly find:
    - Step-by-step remediation from runbooks
    - Troubleshooting guidance for common alerts
    - Escalation and rollback procedures
    """)

    st.divider()
    st.header("💡 Sample Queries")
    sample_queries = [
        "How do I resolve OOMKilled pods in Kubernetes?",
        "Steps to handle high CPU alert on a Linux server?",
        "Database connection pool exhausted - what to do?",
        "How to respond to a disk space alert?",
        "DNS resolution is failing intermittently - how to debug?",
        "Suspicious login from an unknown IP - what now?",
    ]
    for q in sample_queries:
        if st.button(q, width="stretch"):
            st.session_state["prefill"] = q

    st.divider()
    if st.button("🗑️ Clear Chat History", width="stretch"):
        st.session_state.messages = []
        st.rerun()


def _badge_html(agent):
    """Coloured pill for an agent (emoji + name)."""
    return (
        f'<span style="background-color:{agent.color};color:white;padding:3px 10px;'
        f'border-radius:12px;font-size:0.85em;font-weight:600;">{agent.emoji} {agent.name}</span>'
    )


def render_routing_trace(domain, fell_back=False):
    """Show the Router -> Specialist handoff above an answer."""
    agent = get_agent(domain)
    st.markdown(f'🧭 <b>Router</b> &nbsp;→&nbsp; {_badge_html(agent)}', unsafe_allow_html=True)
    if fell_back:
        st.caption("⚠️ No domain-specific runbook matched — General Agent searched all runbooks.")


# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant" and message.get("domain"):
            render_routing_trace(message["domain"], message.get("fell_back", False))
        st.markdown(message["content"])

# Handle prefill from sidebar buttons
prefill_value = st.session_state.pop("prefill", None)

# Chat input
user_input = st.chat_input("Describe your incident or ask about a runbook...")
if prefill_value:
    user_input = prefill_value

if user_input:
    # Show user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Generate response
    with st.chat_message("assistant"):
        try:
            # 1. Route: the Router classifies the query and picks a specialist
            with st.spinner("🧭 Router classifying the incident..."):
                agent = ROUTER.route(user_input)

            # 2. The chosen specialist answers from its own runbooks
            with st.spinner(f"{agent.emoji} {agent.name} searching {agent.domain} runbooks..."):
                result = agent.run(user_input)
            sources = result.get("source_documents", [])

            # 3. Misroute fallback: if the specialist had no matching runbook,
            #    hand off to the General agent (searches all runbooks).
            fell_back = False
            if not sources and agent.domain != "general":
                agent = get_agent("general")
                with st.spinner("🧭 No domain match — General Agent searching all runbooks..."):
                    result = agent.run(user_input)
                sources = result.get("source_documents", [])
                fell_back = True

            response = result["result"]

            # 4. Show the Router -> Specialist handoff (reflects any fallback)
            render_routing_trace(agent.domain, fell_back)

            # Append source documents
            if sources:
                # Normalise separators so a store built on Windows (\) still shows
                # clean filenames when served on Linux (Streamlit Cloud).
                source_names = sorted(set(
                    doc.metadata.get("source", "Unknown").replace("\\", "/").rsplit("/", 1)[-1]
                    for doc in sources
                ))
                response += f"\n\n---\n*Sources: {', '.join(source_names)}*"

            st.markdown(response)
            st.session_state.messages.append({
                "role": "assistant",
                "content": response,
                "domain": agent.domain,
                "fell_back": fell_back,
            })

        except Exception as e:
            err = str(e)
            el = err.lower()
            if "chroma" in el or "collection" in el:
                st.error("Knowledge base not found. Please run `python ingest.py` first.")
            elif "429" in err or "resource_exhausted" in el or "quota" in el:
                st.warning("⏳ Gemini rate limit reached (free tier). Wait a minute and try again.")
            else:
                st.error(f"Error: {err}")
