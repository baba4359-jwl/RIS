import re
from dataclasses import dataclass, field

import nltk

from src.ingestion import Document

nltk.download("punkt", quiet=True)
nltk.download("punkt_tab", quiet=True)

CHUNK_TOKENS = 512
OVERLAP_TOKENS = 64

# Matches "Full Term (ABBR)" patterns, e.g. "typhoid conjugate vaccine (TCV)"
_ABBR_RE = re.compile(r'\b((?:[A-Za-z]\w*(?:\s+[A-Za-z]\w*){0,4})\s+)\(([A-Z][A-Z0-9]{1,5})\)')


@dataclass
class Chunk:
    text: str
    source_file: str
    page_number: int
    chunk_index: int
    abbrev_map: dict[str, str] = field(default_factory=dict)


def _count_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def extract_abbreviations(text: str) -> dict[str, str]:
    """Return {ABBR: full_term} from 'Full Term (ABBR)' patterns in text."""
    return {m.group(2): m.group(1).strip() for m in _ABBR_RE.finditer(text)}


def _augment_text(text: str, abbrev_map: dict[str, str]) -> str:
    """Append expansion hints for abbreviations that appear in the chunk text.

    Ensures BM25 indexes both 'TCV' and 'typhoid conjugate vaccine' in the
    same chunk, so queries using either form receive a non-zero BM25 score.
    """
    if not abbrev_map:
        return text
    hints = [f"{abbr}: {full}" for abbr, full in abbrev_map.items()
             if re.search(rf'\b{re.escape(abbr)}\b', text)]
    return text + " [" + "; ".join(hints) + "]" if hints else text


def chunk_document(
    doc: Document,
    chunk_tokens: int = CHUNK_TOKENS,
    overlap_tokens: int = OVERLAP_TOKENS,
    abbrev_map: dict[str, str] | None = None,
) -> list[Chunk]:
    abbrev_map = abbrev_map or {}
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

        raw_text = " ".join(sentences[start:end])
        chunks.append(Chunk(
            text=_augment_text(raw_text, abbrev_map),
            source_file=doc.source_file,
            page_number=doc.page_number,
            chunk_index=chunk_idx,
            abbrev_map=abbrev_map,
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


def chunk_documents(docs: list[Document]) -> tuple[list[Chunk], dict[str, str]]:
    """Chunk all documents and return (chunks, global_abbrev_map).

    The global abbreviation map is built from all pages before chunking so
    that an abbreviation defined on page 1 is resolved in chunks on page 10.
    """
    file_abbrevs: dict[str, dict[str, str]] = {}
    for doc in docs:
        page_abbrevs = extract_abbreviations(doc.text)
        file_abbrevs.setdefault(doc.source_file, {}).update(page_abbrevs)

    global_map: dict[str, str] = {}
    for m in file_abbrevs.values():
        global_map.update(m)

    all_chunks: list[Chunk] = []
    for doc in docs:
        abbrev_map = file_abbrevs.get(doc.source_file, {})
        all_chunks.extend(chunk_document(doc, abbrev_map=abbrev_map))
    return all_chunks, global_map
