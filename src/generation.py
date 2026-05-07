import os

GROQ_DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_FREE_MODELS = [
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "gemma2-9b-it",
    "mixtral-8x7b-32768",
]
GROQ_MAX_TOKENS = 2048   # free tier TPM=6000; keep output budget conservative

SYSTEM_PROMPT = """You are a research assistant. \
Your answers must be grounded exclusively in the document excerpts provided with each question.

Strict rules:
1. Use ONLY information from the provided [SOURCE] excerpts — no outside knowledge whatsoever
2. Cite every factual claim inline using the format [filename, p.N]
3. When multiple documents support a point, cite all relevant sources
4. If the answer is absent from the excerpts, reply exactly:
   "Not found in the provided literature."
5. Quote directly from the text when precision matters
6. Never hallucinate statistics, percentages, or numerical data"""


def build_context(chunks: list[dict]) -> str:
    parts = [
        f"[SOURCE: {c['source_file']}, Page {c['page_number']}]\n{c['text']}"
        for c in chunks
    ]
    return "\n\n---\n\n".join(parts)


def _build_messages(question: str, chunks: list[dict]) -> list[dict]:
    context = build_context(chunks)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"<document_excerpts>\n{context}\n</document_excerpts>\n\n"
                f"Question: {question}"
            ),
        },
    ]


def stream_answer_groq(
    api_key: str,
    model: str,
    question: str,
    chunks: list[dict],
):
    """Yield text deltas from Groq cloud API (very fast, free tier available)."""
    try:
        from groq import Groq
    except ImportError:
        raise RuntimeError("groq package not installed. Run: pip install groq")

    client = Groq(api_key=api_key)
    try:
        stream = client.chat.completions.create(
            model=model or GROQ_DEFAULT_MODEL,
            messages=_build_messages(question, chunks),
            stream=True,
            max_tokens=GROQ_MAX_TOKENS,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield delta
    except Exception as e:
        raise RuntimeError(f"Groq API error: {e}") from e


def answer(api_key: str, model: str, question: str, chunks: list[dict]) -> dict:
    """Synchronous call for CLI use."""
    parts = list(stream_answer_groq(api_key, model, question, chunks))
    return {
        "answer": "".join(parts),
        "citations": [
            {"source_file": c["source_file"], "page_number": c["page_number"]}
            for c in chunks
        ],
    }
