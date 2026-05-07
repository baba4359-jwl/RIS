import os

import voyageai

VOYAGE_MODEL = "voyage-3-lite"
_client: voyageai.Client | None = None


def _get_client() -> voyageai.Client:
    global _client
    if _client is None:
        _client = voyageai.Client(api_key=os.getenv("VOYAGE_API_KEY"))
    return _client


def embed_texts(texts: list[str], input_type: str = "document") -> list[list[float]]:
    result = _get_client().embed(texts, model=VOYAGE_MODEL, input_type=input_type)
    return result.embeddings
