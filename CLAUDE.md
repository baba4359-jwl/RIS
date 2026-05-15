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
RIS/
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
└── src/
    ├── __init__.py
    ├── ingestion.py           # PDF parsing and text extraction
    ├── chunking.py            # Chunking strategy and text splitting
    ├── embedding.py           # Embedding model wrapper
    ├── vector_store.py        # ChromaDB interface (upsert, query, delete)
    ├── retrieval.py           # Similarity search + BM25 hybrid + re-ranker
    └── generation.py          # LLM call, prompt construction, citation injection
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
- Guidelines use structured paragraphs with one key recommendation per section. 512 tokens typically captures one full recommendation plus its supporting evidence.
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

### Known Failure Case: BM25 Abbreviation Mismatch

**Query asked:** "What is TCV immunogenicity in school-age children?"

**System response (hybrid mode):** Returned semantically plausible chunks from WHO guidelines about TCV, but missed the Lancet 2019 trial paragraph that used only the full term "typhoid conjugate vaccine" (no acronym). BM25 scored that paragraph zero for the token "TCV".

**Root cause analysis:**

1. **Token disjointness:** BM25 is a bag-of-words model. "TCV" and "typhoid conjugate vaccine" are separate tokens with no overlap. A chunk containing only "typhoid conjugate vaccine" receives a BM25 score of 0 for a query containing "TCV", even though they are identical in meaning.
2. **Definition scattering:** In WHO/Lancet PDFs, an abbreviation is typically defined once (page 1–2) and then used without expansion for the remaining 40+ pages. The chunk holding the definition has high BM25 relevance for both forms; subsequent chunks have zero relevance for the full-form query.
3. **Mitigation applied:**
   - `chunking.py`: `extract_abbreviations()` scans all pages of a document for `Full Term (ABBR)` patterns before chunking. Each resulting chunk whose text contains a known abbreviation is augmented with `[ABBR: full term]` so BM25 indexes both forms in that chunk.
   - `retrieval.py`: `_expand_query()` loads the persisted abbreviation map from `db/chroma/abbreviations.json` and appends full-term expansions to the BM25 query string before scoring.
   - `vector_store.py`: `save_abbrev_map()` / `load_abbrev_map()` persist the per-corpus abbreviation map alongside the ChromaDB collection.

---

## Evaluation Table

Questions 6–7 are **cross-document synthesis** cases, designed specifically to test whether the system can combine evidence from ≥ 2 distinct source files in a single answer. The **Cross-Doc Recall** column measures the fraction of gold source files that were cited in the response (1.0 = all required sources cited).

| # | Question | Required Sources (Gold) | Expected Answer | System Response | Result | Cross-Doc Recall | Comment |
|---|---|---|---|---|---|---|---|
| 1 | What are WHO's first-line antibiotic recommendations for uncomplicated typhoid fever in adults? | WHO Typhoid Guidelines 2018 | Azithromycin (orally) or fluoroquinolones where susceptible (p.22) | Correctly cited azithromycin and fluoroquinolones with dosing details | ✅ Hit | N/A (single-source) | Strong retrieval; citation page number matched |
| 2 | What is the reported efficacy of typhoid conjugate vaccine (TCV) in children aged 9 months–15 years? | Lancet 2019 | 81.6% efficacy at 12 months follow-up (p.7) | Retrieved correct efficacy figure; missed confidence interval detail | ⚠️ Partial Hit | N/A (single-source) | CI data was chunked into an adjacent chunk; overlap insufficient |
| 3 | Compare typhoid incidence rates between South Asia and Sub-Saharan Africa per 100,000 population | GBD Typhoid 2019 | South Asia: 493 / Sub-Saharan Africa: 125 per 100,000 (p.4) | Returned correct figures with correct source citation | ✅ Hit | N/A (single-source) | BM25 hybrid search helped surface the numeric comparison |
| 4 | What is the protective efficacy of TCV in infants under 6 months of age? | None (not in literature) | "Not found in the provided literature." | Hallucinated a 72% efficacy figure | ❌ Miss | N/A | Known failure case — see Error Analysis above |
| 5 | What are the clinical criteria distinguishing typhoid fever from paratyphoid fever according to WHO case definitions? | WHO Surveillance Standards | Typhoid: S. Typhi confirmed; Paratyphoid: S. Paratyphi A/B/C (p.9) | Correctly distinguished both case definitions with organism identifiers | ✅ Hit | N/A (single-source) | Re-ranker promoted the case definition chunk over a treatment chunk |
| 6 | How does the WHO 2018 recommended dosing schedule for TCV compare with the immunogenicity findings reported in the Lancet 2019 trial? | WHO Typhoid Guidelines 2018 **+** Lancet 2019 | Single-dose at ≥ 6 months (WHO p.18); 81.6% seroconversion at 12 months post single dose (Lancet p.7) | Pending evaluation — requires both source files | 🔲 Not yet run | Target ≥ 0.8 | Cross-doc synthesis test: answer is incomplete if either source is absent from citations |
| 7 | Contrast the typhoid incidence burden in Sub-Saharan Africa (GBD 2019) with the WHO recommendation on vaccination priority for high-burden regions (WHO Guidelines 2018). | GBD Typhoid 2019 **+** WHO Typhoid Guidelines 2018 | Sub-Saharan Africa: 125/100,000 (GBD p.4); WHO recommends priority rollout in regions > 100/100,000 (WHO p.5) | Pending evaluation — requires both source files | 🔲 Not yet run | Target ≥ 0.8 | Cross-doc synthesis test: confirms retrieval diversity, not single-PDF saturation |

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
- **Cross-document synthesis measurement**: the retrieval pipeline has no per-source diversity cap (`top_k=10` with no ceiling per file). On a small corpus (< 5 PDFs), all 10 retrieved chunks may come from one document, producing a plausible-sounding but single-source answer to a cross-document question. The evaluation table now includes two dedicated cross-doc synthesis cases (Q6, Q7) with a **Cross-Doc Recall** metric. If Cross-Doc Recall < 0.8 on those cases, consider adding a per-source cap (e.g., max 3 chunks per `source_file`) in `retrieval.py`.
- **Abbreviation and metadata priority in BM25**: medical documents define abbreviations once (e.g., "typhoid conjugate vaccine (TCV)") and then use only the short form. Prior to this fix, BM25 treated "TCV" and "typhoid conjugate vaccine" as disjoint tokens, causing zero recall when query and chunk used different forms. **Mitigation applied** (see Error Analysis): `chunking.py` now augments each chunk with inline expansion hints (`[TCV: typhoid conjugate vaccine]`), and `retrieval.py` expands query abbreviations using a persisted map (`db/chroma/abbreviations.json`) before BM25 scoring. Document-level metadata (titles, section headers) still receive no priority weighting; if this becomes a precision issue, consider storing titles as a separate ChromaDB collection with boosted retrieval weight.

---

## Contact / Maintainer Notes

- All LLM calls route through `generation.py` — this is the single point for prompt changes.
- Do not hardcode API keys anywhere; always read from `.env` via `python-dotenv`.
- When adding new PDF sources, update `evaluation/eval_pairs.json` with at least one new Q&A pair to maintain evaluation coverage.

## Deliverables

| Item | Description | Location |
|---|---|---|
| **Codebase** | Modular pipeline with ingestion, retrieval, and generation logic cleanly separated into independent modules. | `src/` directory — https://github.com/baba4359-jwl/RIS |
| **README** | Windows installation guide, environment variable reference, and system architecture summary. | `README.md` |
| **Design Justification** | Rationale for chunking parameters (512 tokens, 64-token overlap) and embedding model selection (`all-MiniLM-L6-v2`). | **Key Design Decisions** section in this document |
| **Error Analysis** | One documented hallucination case with root cause analysis and mitigations applied. | **Error Analysis** section in this document |