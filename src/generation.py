import google.generativeai as genai
from google.generativeai.types import GenerationConfig

MODEL = "gemini-2.0-flash"
MAX_TOKENS = 4096

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


def stream_answer(
    api_key: str,
    history: list[dict],
    question: str,
    chunks: list[dict],
):
    """Yield text deltas from Gemini."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=MODEL,
        system_instruction=SYSTEM_PROMPT,
    )

    contents = []
    for msg in history:
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    context = build_context(chunks)
    contents.append({
        "role": "user",
        "parts": [{"text": (
            f"<document_excerpts>\n{context}\n</document_excerpts>\n\n"
            f"Question: {question}"
        )}],
    })

    response = model.generate_content(
        contents,
        stream=True,
        generation_config=GenerationConfig(max_output_tokens=MAX_TOKENS),
    )

    for chunk in response:
        if chunk.text:
            yield chunk.text


def answer(api_key: str, question: str, chunks: list[dict]) -> dict:
    """Synchronous call for CLI use."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=MODEL,
        system_instruction=SYSTEM_PROMPT,
    )

    context = build_context(chunks)
    response = model.generate_content(
        f"<document_excerpts>\n{context}\n</document_excerpts>\n\nQuestion: {question}",
        generation_config=GenerationConfig(max_output_tokens=MAX_TOKENS),
    )

    return {
        "answer": response.text,
        "citations": [
            {"source_file": c["source_file"], "page_number": c["page_number"]}
            for c in chunks
        ],
    }
