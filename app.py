import os

import anthropic
import fitz  # PyMuPDF
import streamlit as st
from dotenv import load_dotenv
from rank_bm25 import BM25Okapi

load_dotenv()

MODEL = "claude-opus-4-7"
TOP_K = 15

SYSTEM_PROMPT = """You are a research assistant. Your answers must be grounded exclusively \
in the document excerpts provided with each question.

Strict rules:
1. Use ONLY information from the provided [SOURCE] excerpts — no outside knowledge whatsoever
2. Cite every factual claim inline using the format [filename, p.N]
3. When multiple documents support a point, cite all relevant sources
4. If the answer is absent from the excerpts, reply exactly:
   "This information is not found in the uploaded documents."
5. Quote directly from the text when precision matters"""


# ── PDF helpers ──────────────────────────────────────────────────────────────

def parse_pdf(file_bytes: bytes, filename: str) -> list[dict]:
    """Return one dict per non-empty page: {text, source, page}."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    chunks = []
    for page_num in range(len(doc)):
        text = doc[page_num].get_text().strip()
        if len(text) > 100:
            chunks.append({"text": text, "source": filename, "page": page_num + 1})
    doc.close()
    return chunks


def rebuild_index(chunks: list[dict]) -> BM25Okapi:
    tokenized = [c["text"].lower().split() for c in chunks]
    return BM25Okapi(tokenized)


def retrieve(query: str, bm25: BM25Okapi, chunks: list[dict], top_k: int = TOP_K) -> list[dict]:
    scores = bm25.get_scores(query.lower().split())
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    return [chunks[i] for i, score in ranked[:top_k] if score > 0]


def build_context(chunks: list[dict]) -> str:
    parts = [
        f"[SOURCE: {c['source']}, Page {c['page']}]\n{c['text']}"
        for c in chunks
    ]
    return "\n\n---\n\n".join(parts)


# ── Claude streaming ──────────────────────────────────────────────────────────

def stream_claude(
    client: anthropic.Anthropic,
    history: list[dict],
    question: str,
    context: str,
):
    """
    Yield text deltas from Claude.

    history  – clean Q&A pairs (no context injected); provides conversational continuity
    question – current user question
    context  – BM25-retrieved excerpts for the current question only
    """
    # Reconstruct previous turns with their clean text only
    api_msgs = [{"role": m["role"], "content": m["content"]} for m in history]

    # Current turn gets fresh retrieved context
    api_msgs.append({
        "role": "user",
        "content": (
            f"<document_excerpts>\n{context}\n</document_excerpts>\n\n"
            f"Question: {question}"
        ),
    })

    with client.messages.stream(
        model=MODEL,
        max_tokens=8192,
        # Cache the system prompt — stable across all turns
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=api_msgs,
    ) as stream:
        yield from stream.text_stream


# ── Streamlit app ─────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="PDF Research Chatbot",
        page_icon="📄",
        layout="wide",
    )
    st.title("📄 PDF Research Chatbot")
    st.caption(
        "Upload academic papers and ask questions — every answer is grounded "
        "only in the uploaded content, with inline citations."
    )

    # Session-state initialisation
    defaults = {
        "chunks": [],         # all page-level chunks across all PDFs
        "bm25": None,         # BM25 index
        "history": [],        # clean {role, content} pairs for display & history
        "loaded": {},         # filename → page count
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ Settings")
        api_key_input = st.text_input(
            "Anthropic API Key",
            value=os.getenv("ANTHROPIC_API_KEY", ""),
            type="password",
            placeholder="sk-ant-...",
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
            new_files = [f for f in uploaded_files if f.name not in st.session_state.loaded]
            if new_files:
                bar = st.progress(0, text="Parsing PDFs…")
                for idx, uf in enumerate(new_files):
                    page_chunks = parse_pdf(uf.read(), uf.name)
                    st.session_state.chunks.extend(page_chunks)
                    st.session_state.loaded[uf.name] = len(page_chunks)
                    bar.progress(
                        (idx + 1) / len(new_files),
                        text=f"Parsed: {uf.name}",
                    )

                bar.progress(1.0, text="Building search index…")
                st.session_state.bm25 = rebuild_index(st.session_state.chunks)
                bar.empty()
                st.success(f"✅ {len(st.session_state.loaded)} paper(s) indexed")

        if st.session_state.loaded:
            st.divider()
            st.subheader("📋 Loaded Papers")
            for fname, n_pages in sorted(st.session_state.loaded.items()):
                st.markdown(f"📄 **{fname}** — {n_pages} pages")
            st.caption(f"Total indexed: {len(st.session_state.chunks)} pages")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Clear Chat", use_container_width=True):
                    st.session_state.history = []
                    st.rerun()
            with col2:
                if st.button("Remove All", use_container_width=True):
                    for key, val in defaults.items():
                        st.session_state[key] = val if not isinstance(val, list | dict) else type(val)()
                    st.rerun()

    # ── Main chat area ────────────────────────────────────────────────────────
    if not st.session_state.loaded:
        st.info("👈 Upload one or more PDF papers in the sidebar to get started.")
        return

    # Render prior conversation
    for msg in st.session_state.history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Accept new input
    question = st.chat_input("Ask a question about the uploaded papers…")
    if not question:
        return

    api_key = api_key_input or os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        st.error("Provide an Anthropic API key in the sidebar or set ANTHROPIC_API_KEY.")
        return

    # Show user message immediately
    with st.chat_message("user"):
        st.markdown(question)

    # BM25 retrieval
    relevant_chunks = retrieve(question, st.session_state.bm25, st.session_state.chunks)

    with st.chat_message("assistant"):
        if not relevant_chunks:
            answer = "This information is not found in the uploaded documents."
            st.markdown(answer)
        else:
            context = build_context(relevant_chunks)
            client = anthropic.Anthropic(api_key=api_key)

            placeholder = st.empty()
            answer = ""
            for delta in stream_claude(client, st.session_state.history, question, context):
                answer += delta
                placeholder.markdown(answer + "▌")
            placeholder.markdown(answer)

            # Collapsible source panel
            source_labels = sorted({f"{c['source']} (p.{c['page']})" for c in relevant_chunks})
            with st.expander(f"📎 {len(source_labels)} source(s) consulted", expanded=False):
                for label in source_labels:
                    st.caption(label)

    # Persist clean Q&A to history
    st.session_state.history.append({"role": "user", "content": question})
    st.session_state.history.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()
