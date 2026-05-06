from dataclasses import dataclass

import nltk

from src.ingestion import Document

nltk.download("punkt", quiet=True)
nltk.download("punkt_tab", quiet=True)

CHUNK_TOKENS = 512
OVERLAP_TOKENS = 64


@dataclass
class Chunk:
    text: str
    source_file: str
    page_number: int
    chunk_index: int


def _count_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def chunk_document(
    doc: Document,
    chunk_tokens: int = CHUNK_TOKENS,
    overlap_tokens: int = OVERLAP_TOKENS,
) -> list[Chunk]:
    sentences = nltk.sent_tokenize(doc.text)
    if not sentences:
        sentences = [doc.text]
    token_counts = [_count_tokens(s) for s in sentences]

    chunks: list[Chunk] = []
    chunk_idx = 0
    start = 0

    while start < len(sentences):
        end = start
        total = 0
        while end < len(sentences) and total + token_counts[end] <= chunk_tokens:
            total += token_counts[end]
            end += 1

        if end == start:
            end = start + 1

        chunks.append(Chunk(
            text=" ".join(sentences[start:end]),
            source_file=doc.source_file,
            page_number=doc.page_number,
            chunk_index=chunk_idx,
        ))
        chunk_idx += 1

        if end >= len(sentences):
            break

        next_start = end
        overlap_count = 0
        for i in range(end - 1, start - 1, -1):
            if overlap_count + token_counts[i] <= overlap_tokens:
                overlap_count += token_counts[i]
                next_start = i
            else:
                break

        start = next_start if start < next_start < end else end

    return chunks


def chunk_documents(docs: list[Document]) -> list[Chunk]:
    all_chunks: list[Chunk] = []
    for doc in docs:
        all_chunks.extend(chunk_document(doc))
    return all_chunks
