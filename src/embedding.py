from __future__ import annotations

from typing import Callable, Optional

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

ProgressCallback = Optional[Callable[..., None]]

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_texts(
    texts: list[str],
    input_type: str = "document",
    *,
    progress_cb: ProgressCallback = None,
) -> list[list[float]]:
    if not texts:
        return []
    embeddings = _get_model().encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return [e.tolist() for e in embeddings]
