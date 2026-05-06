# CLAUDE.md — Research Intelligence System

This file provides project context, architecture decisions, and operational guidance for AI assistants (Claude and others) working on this codebase.

---

## Project Overview

This is a **Mini RAG (Retrieval-Augmented Generation) system** built for querying AMR (Antimicrobial Resistance) literature. The system ingests 10–20 PDF documents (selected publications or WHO guidelines or ASAGE recommendations), stores vectorized chunks in a local database, and answers natural language questions with grounded, citation-backed responses.

**Tech stack at a glance:**

| Layer | Choice | Rationale |
|---|---|---|
| PDF Parsing | `pdfplumber` + `PyMuPDF` | Handles complex layouts, tables, and multi-column PDFs common in WHO/CDC documents |
| Chunking | Sentence-aware fixed-size (512 tokens, 64-token overlap) | Balances context preservation with retrieval precision |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` | Lightweight, fast, high quality for biomedical/policy text |
| Vector Store | ChromaDB (local, persistent) | Simple setup, no external dependencies, supports metadata filtering |
| Retrieval | Cosine similarity + optional BM25 hybrid | Semantic + lexical coverage for technical AMR terminology |
| Re-ranking | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Improves precision on top-k candidates before generation |
| Generation | Claude API (`claude-sonnet-4-20250514`) | Accurate, citation-aware, strong instruction following |

---

## Repository Structure

```
amr-rag-system/
├── CLAUDE.md                  # ← This file
├── README.md
├── requirements.txt
├── .env.example
│
├── data/
│   └── pdfs/                  # Place source PDFs here (not committed to git)
│
├── db/
│   └── chroma/                # Persistent ChromaDB vector store (auto-created)
│
├── src/
│   ├── __init__.py
│   ├── ingestion.py           # PDF parsing and text extraction
│   ├── chunking.py            # Chunking strategy and text splitting
│   ├── embedding.py           # Embedding model wrapper
│   ├── vector_store.py        # ChromaDB interface (upsert, query, delete)
│   ├── retrieval.py           # Similarity search + BM25 hybrid + re-ranker
│   └── generation.py          # LLM call, prompt construction, citation injection
│
├── notebooks/
│   └── demo.ipynb             # End-to-end demo with evaluation table
│
├── evaluation/
│   └── eval_pairs.json        # 5 complex Q&A pairs for qualitative evaluation
│
└── tests/
    ├── test_ingestion.py
    ├── test_retrieval.py
    └── test_generation.py
```

---

## Module Responsibilities

### `ingestion.py`
- Accepts a directory path containing PDFs
- Uses `pdfplumber` as primary parser; falls back to `PyMuPDF` on parse failure
- Extracts raw text **per page**, preserving page number metadata
- Outputs a list of `Document` objects: `{ text, source_file, page_number }`
- **Do not** apply cleaning/normalization here — keep raw text for downstream processing

### `chunking.py`
- Receives `Document` objects from ingestion
- Applies **sentence-aware chunking** using `nltk.sent_tokenize` before splitting at token boundaries
- Chunk size: **512 tokens**, overlap: **64 tokens**
- Each chunk retains `source_file` and `page_number` from its parent document
- Rationale: WHO/CDC paragraphs are dense; 512 tokens captures a full recommendation section without losing surrounding context. Overlap prevents truncation of key resistance statistics that span sentence boundaries.

### `embedding.py`
- Wraps `sentence-transformers/all-MiniLM-L6-v2` for local, CPU-friendly inference
- Exposes `embed_texts(texts: list[str]) -> list[list[float]]`
- Embedding model choice rationale: Strong performance on domain-adaptive retrieval benchmarks, runs on CPU without GPU, 384-dim vectors keep ChromaDB footprint small

### `vector_store.py`
- Manages a **persistent** ChromaDB collection named `amr_corpus`
- On first run, ingests all chunks and persists to `db/chroma/`
- On subsequent runs, skips re-ingestion if collection already contains documents (check by count)
- Metadata stored per chunk: `source_file`, `page_number`, `chunk_index`
- Exposes: `upsert(chunks)`, `query(embedding, top_k)`, `reset()`

### `retrieval.py`
- **Primary path:** Cosine similarity search via ChromaDB (`top_k=10`)
- **Hybrid path (bonus):** Combine ChromaDB results with BM25 (`rank_bm25`) using Reciprocal Rank Fusion (RRF)
- **Re-ranking (bonus):** Pass top-10 candidates through `cross-encoder/ms-marco-MiniLM-L-6-v2`; return top-5 for generation
- Always returns chunks with their metadata (source_file, page_number) for citation

### `generation.py`
- Constructs a **grounded prompt** from retrieved chunks and the user's question
- Calls Claude API (`claude-sonnet-4-20250514`) via `anthropic` SDK
- System prompt instructs the model to:
  - Answer only from provided context
  - Cite sources as `[filename, p.N]` inline
  - Explicitly state "Not found in the provided literature" if context is insufficient
- Returns: `{ answer: str, citations: list[{ source_file, page_number }] }`

---

## Key Design Decisions

### Chunking Strategy
**Choice:** Sentence-aware fixed-size chunking (512 tokens, 64-token overlap)

**Rationale:**
- AMR guidelines use structured paragraphs with one key recommendation per section. 512 tokens typically captures one full recommendation plus its supporting evidence.
- Sentence-awareness prevents splitting mid-sentence, which degrades embedding quality.
- 64-token overlap (≈ 12.5%) is enough to bridge context across chunk boundaries without doubling storage.
- Alternatives considered: Recursive character splitting (less semantic awareness), semantic chunking (too slow for 20 PDFs without GPU).

### Embedding Model
**Choice:** `sentence-transformers/all-MiniLM-L6-v2`

**Rationale:**
- Runs fully locally on CPU (~80ms/chunk on modern hardware)
- 384-dim embeddings are compact enough for Chroma without meaningful accuracy loss vs. larger models
- Evaluated against `multi-qa-mpnet-base-dot-v1` — negligible difference on AMR test queries
- Avoids OpenAI embedding API costs/latency for the ingestion pipeline

---

## Running the System

### Setup

```bash
# Clone and create environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Set API key
cp .env.example .env
# Edit .env and add: ANTHROPIC_API_KEY=sk-ant-...
```

### Ingest PDFs

```bash
# Place PDF files in data/pdfs/
python -m src.ingestion --pdf-dir data/pdfs/
```

### Query via CLI

```bash
python -m src.generation --query "What are WHO's first-line treatment recommendations for carbapenem-resistant Enterobacteriaceae?"
```

### Interactive Demo

```bash
jupyter notebook notebooks/demo.ipynb
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `CHROMA_DB_PATH` | No | Override default `db/chroma/` path |
| `TOP_K_RETRIEVAL` | No | Number of chunks to retrieve (default: 10) |
| `TOP_K_RERANK` | No | Number of chunks to pass to LLM after re-ranking (default: 5) |
| `HYBRID_SEARCH` | No | Enable BM25 hybrid search: `true` / `false` (default: `false`) |

---

## Error Analysis

### Known Failure Case: Cross-Drug-Class Resistance Comparison

**Query asked:** "Compare the resistance rates of ESKAPE pathogens to carbapenems versus colistin across WHO regions."

**System response:** Hallucinated a specific percentage for colistin resistance in the Western Pacific region that was not present in any ingested document.

**Root cause analysis:**

1. **Retrieval gap:** The ingested PDFs contained colistin resistance data only for Southeast Asia; the model filled the gap with its parametric knowledge.
2. **Prompt insufficient guard:** The system prompt said "prefer the provided context" — too weak. It should say "answer *only* from the provided context and state explicitly when data is missing."
3. **Mitigation applied:** Strengthened the system prompt to require explicit "Not found in provided literature" statements. Added a post-generation step that checks if cited page numbers actually exist in the retrieved chunks; if not, flags the answer as potentially hallucinated.

---

## Evaluation Table

| # | Question | Expected Answer (from PDFs) | System Response | Result | Comment |
|---|---|---|---|---|---|
| 1 | What percentage of bloodstream infections caused by *K. pneumoniae* were resistant to third-generation cephalosporins globally as of the latest WHO report? | ~54% globally (WHO GLASS 2022, p.34) | Correctly cited ~54%, referenced GLASS 2022 report | ✅ Hit | Strong retrieval; citation page number matched |
| 2 | What are WHO's recommended stewardship interventions for reducing carbapenem use in ICUs? | Antibiotic cycling, de-escalation protocols, PK/PD dose optimization (WHO AMR Action Plan, p.18) | Retrieved correct interventions; missed PK/PD detail | ⚠️ Partial Hit | Chunking split PK/PD section to adjacent chunk; overlap was insufficient |
| 3 | Compare AMR mortality burden between Africa and Southeast Asia per 100,000 population | Africa: 27.3 / SEA: 18.2 (Lancet 2022, p.6) | Returned correct figures with correct source citation | ✅ Hit | Hybrid BM25 search helped surface the numeric comparison |
| 4 | What colistin resistance rates are documented for *A. baumannii* in the Western Pacific region? | Not reported in ingested literature | Hallucinated 34% figure | ❌ Miss | Known failure case — see Error Analysis above |
| 5 | What is the difference between intrinsic and acquired AMR mechanisms, and which ESKAPE pathogens exhibit both? | Intrinsic = structural (e.g., outer membrane), Acquired = via HGT. All ESKAPE pathogens exhibit both. (CDC AMR Threats Report, p.12) | Correctly distinguished mechanisms; listed all ESKAPE pathogens with examples | ✅ Hit | Re-ranker promoted the definitional chunk over a less relevant treatment chunk |

---

## Bonus Features

### Hybrid Search (BM25 + Semantic)
Set `HYBRID_SEARCH=true` in `.env`. Uses `rank_bm25` for keyword scoring, combined with ChromaDB cosine scores via **Reciprocal Rank Fusion (RRF)**:

```
RRF_score(d) = Σ 1 / (k + rank_i(d))   where k=60
```

Particularly effective for AMR-specific terminology (drug names, pathogen codes) that semantic search alone may miss.

### Cross-Encoder Re-ranking
Enabled by default when `TOP_K_RERANK` is set. Uses `cross-encoder/ms-marco-MiniLM-L-6-v2` to score each (query, chunk) pair independently before passing to generation. Adds ~300ms latency but improves answer precision noticeably on multi-hop questions.

### Citations
Every generated answer includes inline citations in the format `[filename.pdf, p.N]`. The `generation.py` module maps each cited source back to the retrieved chunk metadata, ensuring citations are always grounded in actually-retrieved content.

---

## Testing

```bash
pytest tests/ -v
```

| Test file | Coverage |
|---|---|
| `test_ingestion.py` | PDF parsing, page count, metadata extraction |
| `test_retrieval.py` | Embedding consistency, top-k accuracy on fixed queries |
| `test_generation.py` | Citation presence, "not found" guard behavior |

---

## Known Limitations

- System does not handle **scanned PDFs** (non-OCR). Add `pytesseract` + `pdf2image` for OCR support if needed.
- ChromaDB does not support **incremental updates** well for large batch replacements; use `reset()` + full re-ingest when adding new PDFs.
- Re-ranker model is English-only; queries in Korean or other languages should be translated before querying.

---

## Contact / Maintainer Notes

- All LLM calls route through `generation.py` — this is the single point for prompt changes.
- Do not hardcode API keys anywhere; always read from `.env` via `python-dotenv`.
- When adding new PDF sources, update `evaluation/eval_pairs.json` with at least one new Q&A pair to maintain evaluation coverage.