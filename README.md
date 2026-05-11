---
title: PDF Research Intelligence
emoji: 📄
colorFrom: blue
colorTo: indigo
sdk: streamlit
sdk_version: 1.35.0
app_file: app_main.py
pinned: false
---

# 📄 PDF Research Intelligence (RIS)

A RAG system that answers questions with citations from uploaded PDF documents.
Powered by the **Groq free API** for fast cloud inference.

---

## Windows Installation Guide

### Step 1 — Download the Project

Download the ZIP file from the link below.

> Visit **https://github.com/baba4359-jwl/RIS** →
> Click the green **`<> Code`** button → Select **`Download ZIP`**

Extract the downloaded **`RIS-main.zip`** to any location.  
(e.g. `C:\RIS-main`)

> After extraction, you should see files such as `start.bat` and `app_main.py` inside the folder.

### Step 2 — Install Python 3.11

`start.bat` will attempt to install Python automatically, but **manual installation is recommended in advance as auto-install may fail in some environments.**

Download and run the Python **3.11 64-bit** installer from the link below.

> **https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe**
>
> File name: **`python-3.11.9-amd64.exe`** (`amd64` = 64-bit — make sure to download this file)

Check **"Add Python to PATH"** at the bottom of the installer screen, then click **Install Now**.

> ⚠️ Python 3.12 and above are not supported. Please install **3.11** only.

### Step 3 — Run start.bat

**Double-click `start.bat`** in the extracted folder.

`start.bat` will automatically perform the following steps:

| Step | Description |
|---|---|
| [1/4] Python check | Detects Python 3.11 64-bit and validates the version |
| [2/4] Virtual environment | Creates the `.venv` folder (first run only) |
| [3/4] Package installation | Installs from `requirements.txt` **(5–10 min on first run)** |
| [4/4] Configuration | Automatically sets up the `.env` file |

Once setup is complete, a browser window will open automatically and the app will launch.

> **On subsequent runs**, simply double-click `start.bat` to start immediately.

#### Troubleshooting

| Error Message | Solution |
|---|---|
| `Could not install Python automatically` | Manually install Python 3.11 following Step 2, then re-run |
| `32-bit Python detected` | Reinstall using `python-3.11.9-amd64.exe` (remove the 32-bit version first) |
| `Package installation failed` | Delete the `.venv` folder and re-run |

---

## Features

- PDF parsing with pdfplumber + PyMuPDF
- Sentence-aware chunking (512 tokens / 64 overlap)
- ChromaDB vector store
- BM25 + Semantic hybrid search (RRF)
- Voyage AI `rerank-2-lite` re-ranking
- Citation-grounded answers via Groq cloud LLM

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq API key (free at console.groq.com) |
| `VOYAGE_API_KEY` | Yes | Voyage AI key (free at dash.voyageai.com) |
| `GROQ_MODEL` | No | Default: `llama-3.1-8b-instant` |
| `TOP_K_RETRIEVAL` | No | Number of chunks to retrieve (default: 10) |
| `TOP_K_RERANK` | No | Number of chunks passed to LLM after re-ranking (default: 5) |
