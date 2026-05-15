import os

from src.embedding import embed_texts
from src import vector_store

TOP_K_RETRIEVAL = int(os.getenv("TOP_K_RETRIEVAL", "10"))
TOP_K_RERANK = int(os.getenv("TOP_K_RERANK", "5"))

VOYAGE_RERANK_MODEL = "rerank-2-lite"

_voyage_client = None


def _get_voyage_client():
    global _voyage_client
    if _voyage_client is None:
        import voyageai
        _voyage_client = voyageai.Client(api_key=os.getenv("VOYAGE_API_KEY"))
    return _voyage_client


def _expand_query(query: str, db_path: str) -> str:
    """Expand abbreviations in the query using the persisted abbreviation map.

    If the user queries "TCV efficacy", this appends "typhoid conjugate vaccine"
    so BM25 also scores chunks that use only the full term.
    """
    abbrev_map = vector_store.load_abbrev_map(db_path)
    if not abbrev_map:
        return query
    tokens = query.split()
    additions: list[str] = []
    for token in tokens:
        clean = token.upper().strip(".,;:()[]")
        if clean in abbrev_map:
            additions.append(abbrev_map[clean])
    return query + (" " + " ".join(additions) if additions else "")


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
    from rank_bm25 import BM25Okapi

    query_embedding = embed_texts([query])[0]
    semantic = vector_store.query(query_embedding, top_k=top_k, db_path=db_path)

    if not semantic:
        return []

    if hybrid:
        all_docs = vector_store.get_all(db_path=db_path)
        if all_docs:
            bm25 = BM25Okapi([d["text"].lower().split() for d in all_docs])
            expanded_query = _expand_query(query, db_path)
            scores = bm25.get_scores(expanded_query.lower().split())
            ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
            bm25_results = [all_docs[i] for i, s in ranked[:top_k] if s > 0]
            candidates = _rrf([semantic, bm25_results])
        else:
            candidates = semantic
    else:
        candidates = semantic

    if rerank and len(candidates) > 1:
        try:
            texts = [c["text"] for c in candidates]
            result = _get_voyage_client().rerank(
                query, texts, model=VOYAGE_RERANK_MODEL, top_k=TOP_K_RERANK
            )
            candidates = [candidates[r.index] for r in result.results]
        except Exception:
            candidates = candidates[:TOP_K_RERANK]

    return candidates
