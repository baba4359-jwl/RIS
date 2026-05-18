import json
import os
from pathlib import Path

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from src.chunking import Chunk

_ABBREV_FILE = "abbreviations.json"

COLLECTION_NAME = "amr_corpus"


class _NoOpEmbeddingFunction(EmbeddingFunction[Documents]):
    """
    Stub embedding function passed to ChromaDB to bypass its default ONNX
    embedder. We always supply pre-computed embeddings via Voyage AI in
    `upsert()`/`query()`, so this is never actually invoked. Avoiding the
    default also dodges the ``NameError: name 'ONNXMiniLM_L6_V2' is not
    defined`` that occurs in PyInstaller bundles, where ChromaDB's dynamic
    ``pkgutil.iter_modules`` discovery cannot register the ONNX class.
    """

    def __call__(self, input: Documents) -> Embeddings:
        raise RuntimeError(
            "ChromaDB embedding function should not be invoked: "
            "embeddings must be supplied explicitly via Voyage AI."
        )


_NOOP_EF = _NoOpEmbeddingFunction()


def _client(db_path: str) -> chromadb.PersistentClient:
    Path(db_path).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=db_path)


def _collection(client: chromadb.PersistentClient) -> chromadb.Collection:
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
        embedding_function=_NOOP_EF,
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


def save_abbrev_map(abbrev_map: dict[str, str], db_path: str) -> None:
    path = Path(db_path) / _ABBREV_FILE
    with open(path, "w", encoding="utf-8") as f:
        json.dump(abbrev_map, f, ensure_ascii=False, indent=2)


def load_abbrev_map(db_path: str) -> dict[str, str]:
    path = Path(db_path) / _ABBREV_FILE
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


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
