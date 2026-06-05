"""
rag_chain.py - RAG Q&A Chain
Connects ChromaDB vector store to Gemini LLM via LangChain for
retrieval-augmented generation (RAG) responses.
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_classic.chains import RetrievalQA
from langchain_core.prompts import PromptTemplate

load_dotenv()

CHROMA_DIR = "./chroma_db"

# Embedding model — MUST match what ingest.py used to build the vector store,
# or retrieval will fail with a dimension mismatch. ingest.py imports this.
EMBEDDING_MODEL = "models/gemini-embedding-2"

PROMPT_TEMPLATE = """
You are an expert AIOps assistant helping IT on-call engineers resolve incidents quickly.
Use the runbook and knowledge base context below to give clear, step-by-step guidance.

If the context does not contain specific information about the issue, say:
"I don't have a specific runbook for this, but here is general guidance:" 
and then provide helpful advice based on IT best practices.

Always:
- Give numbered, actionable steps
- Mention any rollback or escalation steps if relevant
- Keep the tone calm and professional

Context from Runbooks:
{context}

Engineer Query:
{question}

Your Response:
"""


def get_rag_chain():
    """Build and return the RAG chain."""

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "GOOGLE_API_KEY is not set. Copy .env.example to .env and add your "
            "Gemini API key (get one at https://aistudio.google.com/app/apikey)."
        )

    embeddings = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=api_key
    )

    vectorstore = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings
    )

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=api_key,
        temperature=0.3
    )

    prompt = PromptTemplate(
        template=PROMPT_TEMPLATE,
        input_variables=["context", "question"]
    )

    chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=vectorstore.as_retriever(search_kwargs={"k": 3}),
        chain_type_kwargs={"prompt": prompt},
        return_source_documents=True
    )

    return chain


def get_agent_chain(domain: str):
    """Build a RAG chain whose retriever is scoped to a single domain.

    `domain` matches the `domain` metadata set during ingestion (the runbook
    subfolder name, e.g. "network", "security", "kubernetes"). When `domain` is
    "general", no metadata filter is applied and retrieval searches all runbooks.
    """

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "GOOGLE_API_KEY is not set. Copy .env.example to .env and add your "
            "Gemini API key (get one at https://aistudio.google.com/app/apikey)."
        )

    embeddings = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=api_key
    )

    vectorstore = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings
    )

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=api_key,
        temperature=0.3
    )

    prompt = PromptTemplate(
        template=PROMPT_TEMPLATE,
        input_variables=["context", "question"]
    )

    # Scope retrieval to the requested domain; "general" searches everything.
    search_kwargs = {"k": 3}
    if domain and domain != "general":
        search_kwargs["filter"] = {"domain": domain}

    chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=vectorstore.as_retriever(search_kwargs=search_kwargs),
        chain_type_kwargs={"prompt": prompt},
        return_source_documents=True
    )

    return chain
