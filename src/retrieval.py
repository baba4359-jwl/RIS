import os

from rank_bm25 import BM25Okapi

from src.embedding import embed_texts
from src import vector_store

TOP_K_RETRIEVAL = int(os.getenv("TOP_K_RETRIEVAL", "10"))
TOP_K_RERANK = int(os.getenv("TOP_K_RERANK", "5"))

_reranker = None


def _get_reranker():
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder
        _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _reranker


def _rrf(lists: list[list[dict]], k: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion across multiple ranked result lists."""
    scores: dict[str, float] = {}
    items: dict[str, dict] = {}
    for ranked in lists:
        for rank, item in enumerate(ranked):
            key = f"{item['source_file']}__p{item['page_number']}__c{item['chunk_index']}"
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            items[key] = item
    return [items[k] for k in sorted(scores, key=lambda x: scores[x], reverse=True)]


def retrieve(
    query: str,
    top_k: int = TOP_K_RETRIEVAL,
    hybrid: bool = False,
    rerank: bool = True,
    db_path: str = "db/chroma",
) -> list[dict]:
    query_embedding = embed_texts([query])[0]
    semantic = vector_store.query(query_embedding, top_k=top_k, db_path=db_path)

    if not semantic:
        return []

    if hybrid:
        all_docs = vector_store.get_all(db_path=db_path)
        if all_docs:
            bm25 = BM25Okapi([d["text"].lower().split() for d in all_docs])
            scores = bm25.get_scores(query.lower().split())
            ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
            bm25_results = [all_docs[i] for i, s in ranked[:top_k] if s > 0]
            candidates = _rrf([semantic, bm25_results])
        else:
            candidates = semantic
    else:
        candidates = semantic

    if rerank and len(candidates) > 1:
        try:
            ranker = _get_reranker()
            pairs = [(query, c["text"]) for c in candidates]
            rerank_scores = ranker.predict(pairs)
            sorted_pairs = sorted(zip(rerank_scores, candidates), key=lambda x: x[0], reverse=True)
            candidates = [c for _, c in sorted_pairs[:TOP_K_RERANK]]
        except Exception:
            candidates = candidates[:TOP_K_RERANK]

    return candidates
