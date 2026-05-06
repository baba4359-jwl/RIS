import os
from pathlib import Path

import chromadb

from src.chunking import Chunk

COLLECTION_NAME = "amr_corpus"


def _client(db_path: str) -> chromadb.PersistentClient:
    Path(db_path).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=db_path)


def _collection(client: chromadb.PersistentClient) -> chromadb.Collection:
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def upsert(chunks: list[Chunk], embeddings: list[list[float]], db_path: str):
    col = _collection(_client(db_path))
    col.upsert(
        ids=[f"{c.source_file}__p{c.page_number}__c{c.chunk_index}" for c in chunks],
        embeddings=embeddings,
        metadatas=[
            {"source_file": c.source_file, "page_number": c.page_number, "chunk_index": c.chunk_index}
            for c in chunks
        ],
        documents=[c.text for c in chunks],
    )


def query(embedding: list[float], top_k: int, db_path: str) -> list[dict]:
    col = _collection(_client(db_path))
    n = col.count()
    if n == 0:
        return []
    results = col.query(
        query_embeddings=[embedding],
        n_results=min(top_k, n),
        include=["documents", "metadatas", "distances"],
    )
    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append({
            "text": doc,
            "source_file": meta["source_file"],
            "page_number": meta["page_number"],
            "chunk_index": meta["chunk_index"],
            "score": 1.0 - dist,
        })
    return chunks


def get_all(db_path: str) -> list[dict]:
    col = _collection(_client(db_path))
    if col.count() == 0:
        return []
    results = col.get(include=["documents", "metadatas"])
    return [
        {
            "text": doc,
            "source_file": meta["source_file"],
            "page_number": meta["page_number"],
            "chunk_index": meta["chunk_index"],
        }
        for doc, meta in zip(results["documents"], results["metadatas"])
    ]


def count(db_path: str) -> int:
    try:
        return _collection(_client(db_path)).count()
    except Exception:
        return 0


def reset(db_path: str):
    try:
        _client(db_path).delete_collection(COLLECTION_NAME)
    except Exception:
        pass


def get_indexed_files(db_path: str) -> dict[str, int]:
    """Return {source_file: unique_page_count} for all indexed content."""
    col = _collection(_client(db_path))
    if col.count() == 0:
        return {}
    results = col.get(include=["metadatas"])
    pages: dict[str, set] = {}
    for meta in results["metadatas"]:
        pages.setdefault(meta["source_file"], set()).add(meta["page_number"])
    return {k: len(v) for k, v in pages.items()}
