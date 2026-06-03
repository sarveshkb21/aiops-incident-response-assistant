"""
app.py - AIOps Incident Response Assistant
Streamlit chat interface powered by RAG (LangChain + Gemini + ChromaDB).
Run with: streamlit run app.py
"""

import os
import streamlit as st
from rag_chain import get_rag_chain

# Page config
st.set_page_config(
    page_title="AIOps Incident Response Assistant",
    page_icon="🚨",
    layout="wide"
)

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
        "Service health check is failing - troubleshooting steps?"
    ]
    for q in sample_queries:
        if st.button(q, use_container_width=True):
            st.session_state["prefill"] = q

    st.divider()
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.rerun()


# Load RAG chain (cached so it loads once)
@st.cache_resource(show_spinner="Loading knowledge base...")
def load_chain():
    return get_rag_chain()


# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
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
        with st.spinner("Searching runbooks and knowledge base..."):
            try:
                chain = load_chain()
                result = chain.invoke({"query": user_input})
                response = result["result"]

                # Append source documents
                sources = result.get("source_documents", [])
                if sources:
                    source_names = list(set([
                        os.path.basename(doc.metadata.get("source", "Unknown"))
                        for doc in sources
                    ]))
                    response += f"\n\n---\n*Sources: {', '.join(source_names)}*"

                st.markdown(response)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response
                })

            except Exception as e:
                err = str(e)
                if "chroma" in err.lower() or "collection" in err.lower():
                    st.error("Knowledge base not found. Please run `python ingest.py` first.")
                else:
                    st.error(f"Error: {err}")
