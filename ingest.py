"""
ingest.py - Document Ingestion Pipeline
Loads runbooks and KB articles, chunks them, and stores in ChromaDB vector store.
Run this ONCE before starting the app, and whenever you add new documents.
"""

import os
from dotenv import load_dotenv
from langchain_community.document_loaders import DirectoryLoader, TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma

from rag_chain import CHROMA_DIR, EMBEDDING_MODEL

load_dotenv()

RUNBOOKS_DIR = "./data/runbooks"


def load_documents():
    """Load .txt and .pdf files from the runbooks directory."""
    documents = []

    # Load .txt runbooks
    txt_loader = DirectoryLoader(
        RUNBOOKS_DIR,
        glob="**/*.txt",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
        show_progress=True
    )
    documents.extend(txt_loader.load())

    # Load .pdf runbooks
    pdf_loader = DirectoryLoader(
        RUNBOOKS_DIR,
        glob="**/*.pdf",
        loader_cls=PyPDFLoader,
        show_progress=True
    )
    documents.extend(pdf_loader.load())

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

    # Chunk documents for better retrieval
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", " ", ""]
    )
    chunks = splitter.split_documents(documents)
    print(f"Split into {len(chunks)} chunks")

    # Gemini embeddings
    print("\nGenerating embeddings with Gemini...")
    embeddings = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )

    # Store in ChromaDB (persisted locally)
    print("Storing in ChromaDB...")
    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_DIR
    )

    print(f"\nSUCCESS: {len(chunks)} chunks stored in ChromaDB")
    print("You can now run: streamlit run app.py")


if __name__ == "__main__":
    ingest()
