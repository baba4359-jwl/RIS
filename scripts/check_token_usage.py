"""
Diagnostic helper: estimate how much a batch of PDFs will cost against
Voyage AI free-tier limits (3 RPM, 10K TPM, 200M total free tokens).

Usage:
    python scripts/check_token_usage.py [pdf_dir]   (defaults to data/pdfs/)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Path setup so the script is runnable from project root.
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from src.ingestion import parse_directory  # noqa: E402
from src.chunking import chunk_documents, _count_tokens  # noqa: E402

FREE_TPM = 10_000
FREE_RPM = 3
FREE_LIFETIME_TOKENS = 200_000_000  # voyage-3 series


def human(n: int) -> str:
    return f"{n:,}"


def main() -> int:
    pdf_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/pdfs")
    if not pdf_dir.is_dir():
        print(f"[error] PDF directory not found: {pdf_dir}")
        return 1

    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"[error] No PDF files in {pdf_dir}")
        return 1

    print(f"Scanning {len(pdf_files)} PDF(s) in {pdf_dir.resolve()}\n")

    docs = parse_directory(pdf_dir)
    if not docs:
        print("[warn] No pages with text content extracted.")
        return 1

    chunks, _ = chunk_documents(docs)
    heuristic_tokens = sum(_count_tokens(c.text) for c in chunks)

    print(f"Pages parsed         : {len(docs):>8}")
    print(f"Chunks produced      : {len(chunks):>8}")
    print(f"Total chars (raw)    : {human(sum(len(d.text) for d in docs)):>8}")
    print(f"Heuristic tokens     : {human(heuristic_tokens):>8}  (chars/4 estimate)")

    # Try the actual Voyage tokenizer if VOYAGE_API_KEY is set.
    try:
        import voyageai

        api_key = os.getenv("VOYAGE_API_KEY")
        if not api_key:
            print("\n[note] VOYAGE_API_KEY not set; skipping exact token count.")
            actual_tokens: int | None = None
        else:
            client = voyageai.Client(api_key=api_key)
            actual_tokens = client.count_tokens(
                [c.text for c in chunks], model="voyage-3-lite"
            )
            print(f"Voyage tokens (exact): {human(actual_tokens):>8}  (voyage-3-lite tokenizer)")
    except Exception as e:
        print(f"\n[note] Could not run voyage tokenizer: {e}")
        actual_tokens = None

    tokens = actual_tokens if actual_tokens is not None else heuristic_tokens
    requests = 1  # current pipeline batches all chunks in a single embed() call

    print()
    print("-" * 64)
    print("Voyage AI free-tier limits (no payment method on file):")
    print(f"  TPM (tokens / min)   : {human(FREE_TPM):>8}")
    print(f"  RPM (requests / min) : {human(FREE_RPM):>8}")
    print(f"  Lifetime free tokens : {human(FREE_LIFETIME_TOKENS):>8}  (per voyage-3* model)")
    print("-" * 64)

    over_tpm = tokens - FREE_TPM
    print(
        f"\nThis batch tries to embed {human(tokens)} tokens in {requests} request(s)."
    )
    if over_tpm > 0:
        print(
            f"  -> Exceeds TPM by {human(over_tpm)} tokens "
            f"({tokens / FREE_TPM:.1f}x the limit)"
        )
        print(
            f"  -> Free tier needs ~{tokens / FREE_TPM:.1f} minute(s) of throttled "
            "calls to drain this batch under TPM."
        )
    else:
        print(f"  -> TPM OK ({tokens} <= {FREE_TPM})")

    if requests > FREE_RPM:
        print(
            f"  -> Exceeds RPM ({requests} > {FREE_RPM}); split across minutes."
        )
    else:
        print(f"  -> RPM OK ({requests} <= {FREE_RPM})")

    # Per-PDF breakdown
    print("\nPer-PDF breakdown:")
    by_file: dict[str, list] = {}
    for c in chunks:
        by_file.setdefault(c.source_file, []).append(c)

    for fname, file_chunks in sorted(by_file.items()):
        ftoks = sum(_count_tokens(c.text) for c in file_chunks)
        print(
            f"  {fname:<40}  chunks={len(file_chunks):>4}  "
            f"~tokens={human(ftoks):>9}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
