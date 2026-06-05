"""
ingest.py - Document Ingestion Pipeline
Loads runbooks and KB articles, chunks them, and stores in ChromaDB vector store.
Run this ONCE before starting the app, and whenever you add new documents.
"""

import os
import shutil
import stat
import time
from dotenv import load_dotenv
from langchain_community.document_loaders import DirectoryLoader, TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma

from rag_chain import CHROMA_DIR, EMBEDDING_MODEL

load_dotenv()

RUNBOOKS_DIR = "./data/runbooks"


def remove_store(path, attempts=4):
    """Delete the vector-store directory, tolerating transient Windows locks.

    On Windows (especially under OneDrive), a folder can be briefly locked by a
    sync/indexer/antivirus handle, causing PermissionError. We clear read-only
    flags and retry a few times before giving up.
    """
    def _onexc(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)  # clear read-only, then retry the operation
        func(p)

    for i in range(attempts):
        try:
            shutil.rmtree(path, onexc=_onexc)
            return
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(0.7)


def domain_for(source_path):
    """Derive the domain from the immediate subfolder under RUNBOOKS_DIR.

    e.g. data/runbooks/network/runbook_dns_failure.txt -> "network".
    Files placed directly in RUNBOOKS_DIR (no subfolder) are tagged "general".
    """
    rel = os.path.relpath(source_path, RUNBOOKS_DIR)
    parts = rel.split(os.sep)
    return parts[0] if len(parts) > 1 else "general"


def load_documents():
    """Recursively load .txt and .pdf files from RUNBOOKS_DIR and its subfolders,
    tagging each with a `domain` metadata field based on its subfolder."""
    documents = []

    # Load .txt runbooks (recursive — walks all subfolders)
    txt_loader = DirectoryLoader(
        RUNBOOKS_DIR,
        glob="**/*.txt",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
        show_progress=True
    )
    documents.extend(txt_loader.load())

    # Load .pdf runbooks (recursive — walks all subfolders)
    pdf_loader = DirectoryLoader(
        RUNBOOKS_DIR,
        glob="**/*.pdf",
        loader_cls=PyPDFLoader,
        show_progress=True
    )
    documents.extend(pdf_loader.load())

    # Tag each document with its domain (immediate subfolder name)
    for doc in documents:
        doc.metadata["domain"] = domain_for(doc.metadata.get("source", ""))

    return documents


def ingest():
    print("=" * 50)
    print("AIOps Assistant - Document Ingestion")
    print("=" * 50)

    if not os.getenv("GOOGLE_API_KEY"):
        print("ERROR: GOOGLE_API_KEY is not set.")
        print("Copy .env.example to .env and add your Gemini API key")
        print("(get one at https://aistudio.google.com/app/apikey).")
        return

    documents = load_documents()
    if not documents:
        print("ERROR: No documents found in", RUNBOOKS_DIR)
        print("Add .txt or .pdf runbook files and try again.")
        return

    print(f"\nLoaded {len(documents)} document(s)")

    # Show how many documents were found per domain (subfolder)
    domain_counts = {}
    for doc in documents:
        d = doc.metadata.get("domain", "general")
        domain_counts[d] = domain_counts.get(d, 0) + 1
    for d in sorted(domain_counts):
        print(f"  - {d}: {domain_counts[d]} document(s)")

    # Chunk documents for better retrieval (chunks inherit the domain metadata)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", " ", ""]
    )
    chunks = splitter.split_documents(documents)
    print(f"Split into {len(chunks)} chunks")

    # Delete any existing vector store so a rebuild does not duplicate documents
    if os.path.exists(CHROMA_DIR):
        print(f"Removing existing vector store at {CHROMA_DIR} ...")
        try:
            remove_store(CHROMA_DIR)
        except PermissionError:
            print()
            print(f"ERROR: Could not delete {CHROMA_DIR} (access denied).")
            print("Something is holding the folder open. Most likely causes:")
            print("  1. The Streamlit app is still running -> stop it (Ctrl+C) and retry.")
            print("  2. OneDrive is syncing the folder -> pause OneDrive sync and retry.")
            print("  3. File Explorer or an editor has the folder open -> close it and retry.")
            print("Then run `python ingest.py` again.")
            return

    # Gemini embeddings
    print("\nGenerating embeddings with Gemini...")
    embeddings = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )

    # Store in ChromaDB (persisted locally), retrying on transient 429 rate limits
    print("Storing in ChromaDB...")
    delays = [20, 40, 60]  # seconds between retries
    for attempt in range(len(delays) + 1):
        try:
            Chroma.from_documents(
                documents=chunks,
                embedding=embeddings,
                persist_directory=CHROMA_DIR
            )
            break
        except Exception as e:
            msg = str(e)
            rate_limited = "429" in msg or "RESOURCE_EXHAUSTED" in msg
            if rate_limited and attempt < len(delays):
                wait = delays[attempt]
                print(f"  Rate limited by Gemini (429). Waiting {wait}s and retrying "
                      f"({attempt + 1}/{len(delays)}) ...")
                # Clear any partial store before retrying to avoid duplicates
                if os.path.exists(CHROMA_DIR):
                    try:
                        remove_store(CHROMA_DIR)
                    except PermissionError:
                        pass
                time.sleep(wait)
                continue
            if rate_limited:
                print()
                print("ERROR: Gemini embedding quota exhausted (429).")
                print("This is a free-tier rate/quota limit. Options:")
                print("  - Wait a few minutes (per-minute limit) and re-run `python ingest.py`.")
                print("  - If it persists, you have hit the daily free-tier cap: wait for")
                print("    it to reset, or enable billing on your Google API key.")
                return
            raise

    print(f"\nSUCCESS: {len(chunks)} chunks stored in ChromaDB")
    print("You can now run: streamlit run app.py")


if __name__ == "__main__":
    ingest()
