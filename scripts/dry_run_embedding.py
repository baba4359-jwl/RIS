"""
Dry-run the embedding pipeline against the PDFs in ``data/pdfs/``.

The Voyage HTTP call is replaced with a stub so the run is free and
finishes instantly, while ``time.sleep`` is monkeypatched to record
intended pauses without actually waiting. The output shows the batch
plan, the simulated wait sequence, and the cumulative throttle budget.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from src.ingestion import parse_directory  # noqa: E402
from src.chunking import chunk_documents  # noqa: E402
from src import embedding as emb_mod  # noqa: E402


class _FakeResult:
    def __init__(self, embeddings):
        self.embeddings = embeddings


class _FakeClient:
    """Wraps the real client to keep the local tokenizer and stub embed()."""

    def __init__(self, real):
        self._real = real

    def tokenize(self, texts, model):
        return self._real.tokenize(texts, model)

    def embed(self, texts, model, input_type):
        return _FakeResult([[0.1] * 512 for _ in texts])


def main() -> None:
    docs = parse_directory("data/pdfs")
    chunks, _ = chunk_documents(docs)
    texts = [c.text for c in chunks]
    print(f"Chunks: {len(chunks)}")
    print(
        f"Settings: TPM={emb_mod.FREE_TPM} RPM={emb_mod.FREE_RPM} "
        f"safety={emb_mod.TPM_SAFETY} max_per_batch={emb_mod.MAX_TOKENS_PER_BATCH}"
    )

    real = emb_mod._get_client()
    emb_mod._client = _FakeClient(real)

    sleeps: list[float] = []
    orig_sleep = time.sleep
    time.sleep = lambda s: sleeps.append(s)  # type: ignore[assignment]

    events: list[dict] = []

    def progress(**kw):
        events.append(kw)

    try:
        embeddings = emb_mod.embed_texts(texts, progress_cb=progress)
    finally:
        time.sleep = orig_sleep  # type: ignore[assignment]

    print(f"Returned {len(embeddings)} embeddings; first len={len(embeddings[0])}")
    print(
        f"Total simulated sleep: {sum(sleeps):.1f}s across {len(sleeps)} pause(s)"
    )

    phase_count: dict[str, int] = {}
    for e in events:
        phase = e.get("phase", "?")
        phase_count[phase] = phase_count.get(phase, 0) + 1
    print("\nPhase counts:")
    for p, c in phase_count.items():
        print(f"  {p:8s}: {c}")

    print("\nBatch plan:")
    for e in events:
        if e.get("phase") == "embed":
            print(
                f"  batch {e['batch']}/{e['total_batches']}: "
                f"{e['tokens']:>6,} tokens"
            )

    waits = [e for e in events if e.get("phase") == "wait"]
    if waits:
        print("\nThrottle pauses:")
        for e in waits:
            print(
                f"  before batch {e['batch']}/{e['total_batches']}: "
                f"{e['wait_s']:.1f}s"
            )
    else:
        print("\nNo throttle pauses (single batch under TPM).")


if __name__ == "__main__":
    main()
