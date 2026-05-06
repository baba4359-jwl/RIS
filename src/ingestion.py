import io
from dataclasses import dataclass
from pathlib import Path

import fitz
import pdfplumber


@dataclass
class Document:
    text: str
    source_file: str
    page_number: int


def parse_pdf_bytes(file_bytes: bytes, filename: str) -> list[Document]:
    try:
        return _plumber_from_bytes(file_bytes, filename)
    except Exception:
        return _pymupdf_from_bytes(file_bytes, filename)


def parse_pdf(path: str | Path) -> list[Document]:
    path = Path(path)
    try:
        return _plumber_from_path(path)
    except Exception:
        return _pymupdf_from_path(path)


def parse_directory(pdf_dir: str | Path) -> list[Document]:
    docs = []
    for pdf_file in sorted(Path(pdf_dir).glob("*.pdf")):
        docs.extend(parse_pdf(pdf_file))
    return docs


# ── pdfplumber ────────────────────────────────────────────────────────────────

def _plumber_from_bytes(file_bytes: bytes, filename: str) -> list[Document]:
    docs = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for i, page in enumerate(pdf.pages):
            text = (page.extract_text() or "").strip()
            if len(text) > 100:
                docs.append(Document(text=text, source_file=filename, page_number=i + 1))
    return docs


def _plumber_from_path(path: Path) -> list[Document]:
    docs = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = (page.extract_text() or "").strip()
            if len(text) > 100:
                docs.append(Document(text=text, source_file=path.name, page_number=i + 1))
    return docs


# ── PyMuPDF fallback ──────────────────────────────────────────────────────────

def _pymupdf_from_bytes(file_bytes: bytes, filename: str) -> list[Document]:
    docs = []
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    for i in range(len(doc)):
        text = doc[i].get_text().strip()
        if len(text) > 100:
            docs.append(Document(text=text, source_file=filename, page_number=i + 1))
    doc.close()
    return docs


def _pymupdf_from_path(path: Path) -> list[Document]:
    docs = []
    doc = fitz.open(str(path))
    for i in range(len(doc)):
        text = doc[i].get_text().strip()
        if len(text) > 100:
            docs.append(Document(text=text, source_file=path.name, page_number=i + 1))
    doc.close()
    return docs
