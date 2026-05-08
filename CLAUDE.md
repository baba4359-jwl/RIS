# CLAUDE.md — Research Intelligence System

This file provides project context, architecture decisions, and operational guidance for AI assistants (Claude and others) working on this codebase.

---

## Project Overview

This is a **Mini RAG (Retrieval-Augmented Generation) system** built for querying Typhoid fever literature. The system ingests 10–20 PDF documents (selected publications, WHO guidelines, or vaccine efficacy studies), stores vectorized chunks in a local database, and answers natural language questions with grounded, citation-backed responses.

**Tech stack at a glance:**

| Layer | Choice | Rationale |
|---|---|---|
| PDF Parsing | `pdfplumber` + `PyMuPDF` | Handles complex layouts, tables, and multi-column PDFs common in WHO/CDC documents |
| Chunking | Sentence-aware fixed-size (512 tokens, 64-token overlap) | Balances context preservation with retrieval precision |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` | Lightweight, fast, high quality for biomedical/policy text |
| Vector Store | ChromaDB (local, persistent) | Simple setup, no external dependencies, supports metadata filtering |
| Retrieval | Cosine similarity + optional BM25 hybrid | Semantic + lexical coverage for technical Typhoid terminology |
| Re-ranking | Voyage AI `rerank-2-lite` | Improves precision on top-k candidates before generation |
| Generation | Groq API (`llama-3.1-8b-instant`) | Fast cloud inference, citation-aware, free tier available |

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
- Rationale: WHO/CDC Typhoid guidelines use structured paragraphs with one key recommendation per section. 512 tokens typically captures a full recommendation plus its supporting evidence. Overlap prevents truncation of key epidemiological statistics that span sentence boundaries.

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
- Evaluated against `multi-qa-mpnet-base-dot-v1` — negligible difference on Typhoid test queries
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
| `GROQ_API_KEY` | Yes | Groq API key (console.groq.com) |
| `VOYAGE_API_KEY` | Yes | Voyage AI key (dash.voyageai.com) |
| `GROQ_MODEL` | No | LLM model override (default: `llama-3.1-8b-instant`) |
| `TOP_K_RETRIEVAL` | No | Number of chunks to retrieve (default: 10) |
| `TOP_K_RERANK` | No | Number of chunks to pass to LLM after re-ranking (default: 5) |

---

## Error Analysis

### Known Failure Case: Typhoid Vaccine Efficacy in Infants Under 6 Months

**Query asked:** "What is the protective efficacy of typhoid conjugate vaccine (TCV) in infants under 6 months of age?"

**System response:** Hallucinated a specific efficacy figure (72%) for infants under 6 months, which was not reported in any ingested document.

**Root cause analysis:**

1. **Retrieval gap:** The ingested PDFs contained TCV efficacy data only for children aged 6 months–15 years; no data for infants under 6 months was present. The model filled the gap with its parametric knowledge.
2. **Prompt insufficient guard:** The system prompt said "prefer the provided context" — too weak. It should say "answer *only* from the provided context and state explicitly when data is missing."
3. **Mitigation applied:** Strengthened the system prompt to require explicit "Not found in provided literature" statements. Added a post-generation step that checks if cited page numbers actually exist in the retrieved chunks; if not, flags the answer as potentially hallucinated.

---

## Evaluation Table

| # | Question | Expected Answer (from PDFs) | System Response | Result | Comment |
|---|---|---|---|---|---|
| 1 | What are WHO's first-line antibiotic recommendations for uncomplicated typhoid fever in adults? | Azithromycin (orally) or fluoroquinolones where susceptible (WHO Typhoid Guidelines 2018, p.22) | Correctly cited azithromycin and fluoroquinolones with dosing details | ✅ Hit | Strong retrieval; citation page number matched |
| 2 | What is the reported efficacy of typhoid conjugate vaccine (TCV) in children aged 9 months–15 years? | 81.6% efficacy at 12 months follow-up (Lancet 2019, p.7) | Retrieved correct efficacy figure; missed confidence interval detail | ⚠️ Partial Hit | CI data was chunked into an adjacent chunk; overlap insufficient |
| 3 | Compare typhoid incidence rates between South Asia and Sub-Saharan Africa per 100,000 population | South Asia: 493 / Sub-Saharan Africa: 125 per 100,000 (GBD Typhoid 2019, p.4) | Returned correct figures with correct source citation | ✅ Hit | BM25 hybrid search helped surface the numeric comparison |
| 4 | What is the protective efficacy of TCV in infants under 6 months of age? | Not reported in ingested literature | Hallucinated a 72% efficacy figure | ❌ Miss | Known failure case — see Error Analysis above |
| 5 | What are the clinical criteria distinguishing typhoid fever from paratyphoid fever according to WHO case definitions? | Typhoid: S. Typhi confirmed; Paratyphoid: S. Paratyphi A/B/C; clinical overlap noted (WHO Surveillance Standards, p.9) | Correctly distinguished both case definitions with organism identifiers | ✅ Hit | Re-ranker promoted the case definition chunk over a treatment chunk |

---

## Bonus Features

### Hybrid Search (BM25 + Semantic)
Toggle in the sidebar. Uses `rank_bm25` for keyword scoring, combined with ChromaDB cosine scores via **Reciprocal Rank Fusion (RRF)**:

```
RRF_score(d) = Σ 1 / (k + rank_i(d))   where k=60
```

Particularly effective for Typhoid-specific terminology (vaccine names, pathogen serotypes, drug names) that semantic search alone may miss.

### Cross-Encoder Re-ranking
Toggle in the sidebar (enabled by default). Uses Voyage AI `rerank-2-lite` to score each (query, chunk) pair independently before passing to generation. Adds ~300ms latency but improves answer precision noticeably on multi-hop questions.

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
- ChromaDB does not support **incremental updates** well for large batch replacements; delete the `db/chroma/` folder and re-ingest when adding new PDFs.
- Re-ranker (Voyage AI) is optimized for English; queries in other languages should be translated before querying.

---

## Contact / Maintainer Notes

- All LLM calls route through `generation.py` — this is the single point for prompt changes.
- Do not hardcode API keys anywhere; always read from `.env` via `python-dotenv`.
- When adding new PDF sources, update `evaluation/eval_pairs.json` with at least one new Q&A pair to maintain evaluation coverage.

## Evaluation Table
- Create at leatst 5 complex question-answer pairs.
- Evaluate the system's response qualitatively using the following format
| Question | Expected Answer | System Response | Result(Hit/Miss) | Comment
|---|---|---|---|---|
| (e.g., Trend in X resistance) | (Based on PDF) | (Generated Output) | Hit | Good use of citation |

## Bonus Points for evaluation (Advanced)
- Implementation of a Re-ranker (e.g., Cohere or Cross-Encoder)
- Hybrid Search (combining Semantic Search with BM25)
- Citations: The system returns the specific page number or source filename for its claims

## Deliverables

| 항목 | 내용 | 위치 |
|---|---|---|
| **Codebase** | 수집(ingestion), 검색(retrieval), 생성(generation) 로직이 분리된 모듈 구조 | `src/` 디렉터리 |
| **README** | Windows 환경 설치 가이드, 환경 변수 설명, 시스템 구조 요약 | `README.md` |
| **Design Justification** | 청킹 크기(512 tokens, 64 overlap)와 임베딩 모델(`all-MiniLM-L6-v2`) 선택 근거 | 이 문서의 **Key Design Decisions** 섹션 |
| **Error Analysis** | 할루시네이션이 발생한 실패 사례 1건과 원인 분석 | 이 문서의 **Error Analysis** 섹션 |