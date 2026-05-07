import os
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from src.ingestion import parse_pdf_bytes, parse_directory
from src.chunking import chunk_documents
from src.embedding import embed_texts
from src import vector_store
from src.retrieval import retrieve
from src.generation import (
    DEFAULT_HOST as OLLAMA_DEFAULT_HOST,
    DEFAULT_MODEL as OLLAMA_DEFAULT_MODEL,
    is_reachable as ollama_is_reachable,
    list_models as ollama_list_models,
    stream_answer,
    stream_answer_groq,
    GROQ_DEFAULT_MODEL,
    GROQ_FREE_MODELS,
)

load_dotenv()

DB_PATH = str(Path("db/chroma").resolve())


# ── Cached resource loaders ───────────────────────────────────────────────────

@st.cache_resource(show_spinner="Loading embedding model (first run may take ~30s)…")
def _load_embedding_model():
    embed_texts(["warmup"])
    return True


@st.cache_resource(show_spinner="Loading re-ranking model…")
def _load_reranker():
    try:
        from sentence_transformers import CrossEncoder
        return CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    except Exception:
        return None


# ── PDF indexing pipeline ─────────────────────────────────────────────────────

def _index_uploaded_files(files) -> tuple[int, int]:
    """Parse → chunk → embed → upsert. Returns (file_count, chunk_count)."""
    progress = st.progress(0.0, text="Parsing PDFs…")
    all_docs = []
    for i, uf in enumerate(files):
        docs = parse_pdf_bytes(uf.read(), uf.name)
        all_docs.extend(docs)
        progress.progress((i + 1) / (len(files) * 3), text=f"Parsed: {uf.name}")

    progress.progress(0.40, text="Chunking documents…")
    chunks = chunk_documents(all_docs)

    progress.progress(0.55, text=f"Embedding {len(chunks)} chunks (may take a moment)…")
    embeddings = embed_texts([c.text for c in chunks])

    progress.progress(0.90, text="Indexing in ChromaDB…")
    vector_store.upsert(chunks, embeddings, DB_PATH)

    progress.progress(1.0, text="Done!")
    time.sleep(0.4)
    progress.empty()
    return len(files), len(chunks)


# ── Main app ──────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="PDF Research Intelligence",
        page_icon="📄",
        layout="wide",
    )

    # Pre-warm embedding model
    _load_embedding_model()

    st.title("📄 PDF Research Intelligence")
    st.caption(
        "Semantic search · BM25 hybrid retrieval · Cross-encoder re-ranking · "
        "Citation-grounded answers"
    )

    # ── Session state ─────────────────────────────────────────────────────────
    if "history" not in st.session_state:
        st.session_state.history = []
    if "indexed_files" not in st.session_state:
        st.session_state.indexed_files = vector_store.get_indexed_files(DB_PATH)

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ Settings")

        st.subheader("⚙️ LLM Provider")
        provider = st.radio(
            "Provider",
            options=["Ollama (Local)", "Groq (Cloud)"],
            index=1 if os.getenv("GROQ_API_KEY") else 0,
            label_visibility="collapsed",
        )

        if provider == "Groq (Cloud)":
            groq_api_key = st.text_input(
                "Groq API Key",
                value=os.getenv("GROQ_API_KEY", ""),
                type="password",
                help="Free tier at console.groq.com — no GPU needed, very fast.",
            )
            env_groq_model = os.getenv("GROQ_MODEL", GROQ_DEFAULT_MODEL)
            default_groq_idx = (
                GROQ_FREE_MODELS.index(env_groq_model)
                if env_groq_model in GROQ_FREE_MODELS
                else 0
            )
            groq_model = st.selectbox(
                "Model",
                options=GROQ_FREE_MODELS,
                index=default_groq_idx,
                help="llama-3.1-8b-instant is fastest; llama-3.3-70b-versatile is highest quality.",
            )
            st.caption("⚡ Cloud inference — responses in 1–3 seconds")
            ollama_host = OLLAMA_DEFAULT_HOST
            ollama_model = OLLAMA_DEFAULT_MODEL
        else:
            groq_api_key = ""
            groq_model = ""
            st.subheader("🦙 Local LLM (Ollama)")
            ollama_host = st.text_input(
                "Ollama host",
                value=os.getenv("OLLAMA_HOST", OLLAMA_DEFAULT_HOST),
                help="URL of the local Ollama daemon. Default: http://localhost:11434",
            )

            available_models = ollama_list_models(ollama_host)
            env_model = os.getenv("OLLAMA_MODEL", OLLAMA_DEFAULT_MODEL)

            if available_models:
                default_idx = (
                    available_models.index(env_model)
                    if env_model in available_models
                    else 0
                )
                ollama_model = st.selectbox(
                    "Model",
                    options=available_models,
                    index=default_idx,
                    help="Locally installed Ollama models. Pull more with `ollama pull <name>`.",
                )
                st.caption("✅ Connected to Ollama")
            else:
                ollama_model = st.text_input(
                    "Model",
                    value=env_model,
                    help="Could not list models. Type the name of a model you've already pulled.",
                )
                st.caption(
                    "⚠️ Ollama not reachable. Install from "
                    "[ollama.com](https://ollama.com) and pull a model, e.g. "
                    "`ollama pull qwen2.5:3b`."
                )

        st.divider()

        hybrid_search = st.toggle(
            "🔀 Hybrid Search",
            value=False,
            help="Combines BM25 keyword scoring with semantic search via Reciprocal Rank Fusion",
        )
        use_reranker = st.toggle(
            "⚡ Cross-Encoder Re-ranking",
            value=True,
            help="Re-scores top candidates with cross-encoder/ms-marco-MiniLM-L-6-v2 for higher precision",
        )

        st.divider()
        st.header("📚 Upload Papers")

        uploaded_files = st.file_uploader(
            "PDF files (10–20 recommended)",
            type="pdf",
            accept_multiple_files=True,
            label_visibility="collapsed",
        )

        if uploaded_files:
            new_files = [f for f in uploaded_files if f.name not in st.session_state.indexed_files]
            if new_files:
                if st.button(
                    f"Index {len(new_files)} new PDF(s)",
                    type="primary",
                    use_container_width=True,
                ):
                    n_files, n_chunks = _index_uploaded_files(new_files)
                    st.session_state.indexed_files = vector_store.get_indexed_files(DB_PATH)
                    st.toast(f"✅ {n_files} file(s) indexed — {n_chunks} chunks", icon="✅")
                    st.rerun()
            else:
                st.success("All uploaded files are already indexed.")

        # ── Indexed papers list ───────────────────────────────────────────────
        if st.session_state.indexed_files:
            st.divider()
            st.subheader("📋 Indexed Papers")
            for fname, n_pages in sorted(st.session_state.indexed_files.items()):
                st.markdown(f"📄 **{fname}** — {n_pages} pages")
            st.caption(f"Total: {vector_store.count(DB_PATH):,} chunks in vector store")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Clear Chat", use_container_width=True):
                    st.session_state.history = []
                    st.rerun()
            with col2:
                if st.button("Reset DB", use_container_width=True, type="secondary"):
                    vector_store.reset(DB_PATH)
                    st.session_state.indexed_files = {}
                    st.session_state.history = []
                    st.rerun()

    # ── Main chat area ────────────────────────────────────────────────────────
    if not st.session_state.indexed_files:
        _render_empty_state()
        return

    # Active retrieval mode badge
    mode_parts = ["Semantic"]
    if hybrid_search:
        mode_parts.append("+ BM25")
    if use_reranker:
        mode_parts.append("+ Re-rank")
    st.caption(f"Retrieval mode: **{' '.join(mode_parts)}**")

    # Conversation history
    for msg in st.session_state.history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    question = st.chat_input("Ask a question about the uploaded papers…")
    if not question:
        return

    if provider == "Groq (Cloud)":
        if not groq_api_key:
            st.error(
                "Groq API 키를 사이드바에 입력하세요. "
                "[console.groq.com](https://console.groq.com)에서 무료로 발급받을 수 있습니다."
            )
            return
    else:
        if not ollama_is_reachable(ollama_host):
            st.error(
                f"Cannot reach Ollama at `{ollama_host}`. "
                "Install from [ollama.com](https://ollama.com), then make sure the "
                "Ollama app is running (or run `ollama serve`)."
            )
            return
        if not ollama_model:
            st.error("Select an Ollama model in the sidebar.")
            return

    with st.chat_message("user"):
        st.markdown(question)

    # Retrieval
    with st.spinner("Searching literature…"):
        if use_reranker:
            _load_reranker()  # ensure reranker is loaded
        chunks = retrieve(
            query=question,
            top_k=int(os.getenv("TOP_K_RETRIEVAL", "10")),
            hybrid=hybrid_search,
            rerank=use_reranker,
            db_path=DB_PATH,
        )

    with st.chat_message("assistant"):
        if not chunks:
            answer = "Not found in the provided literature."
            st.markdown(answer)
        else:
            placeholder = st.empty()
            answer = ""
            try:
                _stream = (
                    stream_answer_groq(groq_api_key, groq_model, [], question, chunks)
                    if provider == "Groq (Cloud)"
                    else stream_answer(ollama_host, ollama_model, [], question, chunks)
                )
                for delta in _stream:
                    answer += delta
                    placeholder.markdown(answer + "▌")
                placeholder.markdown(answer)
            except RuntimeError as e:
                answer = f"⚠️ {e}"
                placeholder.error(answer)

            # Collapsible source panel
            source_labels = sorted({f"{c['source_file']} (p.{c['page_number']})" for c in chunks})
            with st.expander(f"📎 {len(source_labels)} source(s) consulted", expanded=False):
                cols = st.columns(2)
                for i, label in enumerate(source_labels):
                    cols[i % 2].caption(f"• {label}")

    st.session_state.history.append({"role": "user", "content": question})
    st.session_state.history.append({"role": "assistant", "content": answer})


def _render_empty_state():
    st.info("👈 Upload one or more PDF papers in the sidebar to get started.")

    # Auto-detect data/pdfs/ directory
    data_pdfs = Path("data/pdfs")
    if data_pdfs.exists():
        pdf_files = list(data_pdfs.glob("*.pdf"))
        if pdf_files:
            st.info(
                f"Found **{len(pdf_files)} PDF(s)** in `data/pdfs/`. "
                "Upload them via the sidebar to index."
            )

    with st.expander("ℹ️ System architecture", expanded=False):
        st.markdown("""
| Stage | Method |
|---|---|
| PDF parsing | pdfplumber (primary) → PyMuPDF (fallback) |
| Chunking | Sentence-aware, 512 tokens, 64-token overlap |
| Embeddings | `all-MiniLM-L6-v2` (local, CPU) |
| Vector store | ChromaDB (persistent, cosine similarity) |
| Hybrid search | BM25 + semantic via Reciprocal Rank Fusion |
| Re-ranking | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| Generation | Local LLM via Ollama (citation-grounded, no external API) |
        """)


if __name__ == "__main__":
    main()
