# AIOps Incident Response Assistant

A RAG-powered chatbot that helps IT on-call engineers instantly find
remediation steps during incidents using LangChain, ChromaDB, Gemini, and Streamlit.

---

## Tech Stack

| Component       | Tool                        |
|-----------------|-----------------------------|
| LLM             | Google Gemini 2.5 Pro       |
| Embeddings      | Google gemini-embedding-2   |
| Framework       | LangChain 1.x               |
| Vector Store    | ChromaDB (local)            |
| UI              | Streamlit                   |
| Language        | Python 3.10+                |

> **Note on model names:** Google periodically retires Gemini models. If you hit a
> `404 NOT_FOUND` for a model, list the currently available ones and update
> `EMBEDDING_MODEL` in `rag_chain.py` (embeddings) or the `model=` in
> `get_rag_chain()` (LLM). The embedding model **must** be identical in ingest and
> query — it is defined once as `EMBEDDING_MODEL` in `rag_chain.py` and imported by
> `ingest.py` to keep them in sync.

---

## Setup Instructions (Windows)

### Step 1: Clone or create the project folder
```
cd C:\Users\YourName\Documents
mkdir aiops-assistant
cd aiops-assistant
```

### Step 2: Create and activate virtual environment
```
python -m venv venv
venv\Scripts\activate
```

### Step 3: Install dependencies
```
pip install -r requirements.txt
```

### Step 4: Set up your API key
- Copy `.env.example` to `.env`
- Open `.env` and replace `your_gemini_api_key_here` with your actual key
- Get your Gemini API key from: https://aistudio.google.com/app/apikey

### Step 5: Add your runbooks
- Place your `.txt` or `.pdf` runbook files in `data/runbooks/`
- Sample runbooks are already included to get you started

### Step 6: Ingest documents into vector store
```
python ingest.py
```

### Step 7: Launch the app
```
streamlit run app.py
```

The app will open at: http://localhost:8501

---

## Project Structure

```
aiops-assistant/
├── app.py                         # Streamlit UI
├── ingest.py                      # Document ingestion pipeline
├── rag_chain.py                   # RAG Q&A chain (LangChain + Gemini)
├── requirements.txt               # Python dependencies
├── .env.example                   # API key template
├── .env                           # Your actual API key (do not commit)
├── .gitignore
├── data/
│   └── runbooks/                  # Add your runbooks here
│       ├── runbook_oom_kubernetes.txt
│       ├── runbook_high_cpu.txt
│       ├── runbook_database.txt
│       └── runbook_disk_space.txt
└── chroma_db/                     # Auto-created by ingest.py
```

---

## Sample Queries to Test

- How do I resolve OOMKilled pods in Kubernetes?
- Steps to handle high CPU alert on a Linux server?
- Database connection pool exhausted - what to do?
- How to respond to a disk space alert?
- Service health check is failing - troubleshooting steps?

---

## Adding More Runbooks

1. Add your `.txt` or `.pdf` files to `data/runbooks/`
2. Re-run `python ingest.py` to update the vector store
3. Restart the Streamlit app

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `GOOGLE_API_KEY is not set` | No `.env` file or key missing | Copy `.env.example` to `.env` and paste your key |
| `404 NOT_FOUND ... is not found for API version` | The Gemini model name was retired | Update the model name in `rag_chain.py` (see the model note above) |
| `ModuleNotFoundError: No module named 'langchain...'` | Dependencies out of date | Re-run `pip install -r requirements.txt` |
| Answers seem unrelated to your runbooks, or a dimension error on query | Vector store was built with a different embedding model | Delete the `chroma_db/` folder and re-run `python ingest.py` |
| `Knowledge base not found` in the app | `ingest.py` was never run | Run `python ingest.py` before launching the app |

> **Important:** Whenever you change `EMBEDDING_MODEL`, you must delete `chroma_db/`
> and re-ingest. Embeddings from different models are not compatible.

---

## Capstone Project - Build Fast with AI
Author: Sarvesh Bedsur
Course: Gen AI Launch Pad 2026
