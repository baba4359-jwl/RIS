import json
import os

import requests

DEFAULT_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
MAX_TOKENS = 4096
REQUEST_TIMEOUT = 600  # generous: first call may load the model into RAM

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


def _build_messages(history: list[dict], question: str, chunks: list[dict]) -> list[dict]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    context = build_context(chunks)
    messages.append({
        "role": "user",
        "content": (
            f"<document_excerpts>\n{context}\n</document_excerpts>\n\n"
            f"Question: {question}"
        ),
    })
    return messages


def _normalize_host(host: str | None) -> str:
    return (host or DEFAULT_HOST).rstrip("/")


def stream_answer(
    host: str,
    model: str,
    history: list[dict],
    question: str,
    chunks: list[dict],
):
    """Yield text deltas from a local Ollama server (`/api/chat`, streaming)."""
    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": _build_messages(history, question, chunks),
        "stream": True,
        "options": {"num_predict": MAX_TOKENS},
    }

    try:
        resp = requests.post(
            f"{_normalize_host(host)}/api/chat",
            json=payload,
            stream=True,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Could not reach Ollama at {_normalize_host(host)}. "
            "Is the Ollama daemon running? Install from https://ollama.com "
            "and run `ollama serve` (or just launch the Ollama app)."
        ) from e
    except requests.exceptions.HTTPError as e:
        detail = ""
        try:
            detail = e.response.json().get("error", "")
        except Exception:
            detail = e.response.text if e.response is not None else ""
        raise RuntimeError(
            f"Ollama returned an error: {detail or str(e)}. "
            f"If the model isn't installed, run: `ollama pull {model or DEFAULT_MODEL}`."
        ) from e

    with resp:
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            delta = (data.get("message") or {}).get("content", "")
            if delta:
                yield delta
            if data.get("done"):
                break


def stream_answer_groq(
    api_key: str,
    model: str,
    history: list[dict],
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
            messages=_build_messages([], question, chunks),
            stream=True,
            max_tokens=GROQ_MAX_TOKENS,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield delta
    except Exception as e:
        raise RuntimeError(f"Groq API error: {e}") from e


def answer(host: str, model: str, question: str, chunks: list[dict]) -> dict:
    """Synchronous call for CLI use."""
    parts = list(stream_answer(host, model, [], question, chunks))
    return {
        "answer": "".join(parts),
        "citations": [
            {"source_file": c["source_file"], "page_number": c["page_number"]}
            for c in chunks
        ],
    }


def list_models(host: str | None = None) -> list[str]:
    """Return locally-installed Ollama model names. Empty list if unreachable."""
    try:
        resp = requests.get(f"{_normalize_host(host)}/api/tags", timeout=3)
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        return []


def is_reachable(host: str | None = None) -> bool:
    try:
        resp = requests.get(f"{_normalize_host(host)}/api/tags", timeout=2)
        return resp.ok
    except Exception:
        return False
