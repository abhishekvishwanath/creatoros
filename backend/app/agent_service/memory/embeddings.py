"""Local embedding model (CLAUDE.md §6.2 semantic memory).

Runs entirely in-process via fastembed (ONNX, no torch, no API key, no
network call at embed time — only a one-time model download on first use).
BAAI/bge-small-en-v1.5 produces 384-dim vectors, matching the
content_embeddings.embedding column (see migration
d9a1c3e5f7b2_semantic_memory_and_youtube_link.py).

Same "graceful degrade when the dependency isn't usable" precedent as
ModelRouter (§12) and Supabase Auth (deps.py): a failure to embed is logged
and swallowed, never raised into the caller — semantic memory is enrichment
on top of the primary write, not a precondition for it.
"""

import logging
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384
# Generous but bounded — a full video transcript can run tens of thousands
# of characters; the model only attends to the first ~512 tokens anyway, so
# truncating well before that is free and keeps embed calls fast.
MAX_EMBED_CHARS = 4000


@lru_cache
def _get_model():
    from fastembed import TextEmbedding

    return TextEmbedding(EMBEDDING_MODEL_NAME)


def embed_text(text: str) -> Optional[list[float]]:
    """Returns a 384-dim embedding, or None if the model can't be loaded or
    the call otherwise fails (e.g. first-run model download blocked by a
    sandboxed/offline environment)."""
    cleaned = (text or "").strip()
    if not cleaned:
        return None
    try:
        model = _get_model()
        vector = next(iter(model.embed([cleaned[:MAX_EMBED_CHARS]])))
        return vector.tolist()
    except Exception:
        logger.warning("Embedding generation failed; semantic memory write skipped.", exc_info=True)
        return None


def embed_texts(texts: list[str]) -> list[Optional[list[float]]]:
    """Batch form of embed_text — one fastembed call instead of N, same
    all-or-nothing-per-item failure handling."""
    cleaned = [(t or "").strip()[:MAX_EMBED_CHARS] for t in texts]
    non_empty_indices = [i for i, t in enumerate(cleaned) if t]
    if not non_empty_indices:
        return [None] * len(texts)
    try:
        model = _get_model()
        vectors = list(model.embed([cleaned[i] for i in non_empty_indices]))
    except Exception:
        logger.warning("Batch embedding generation failed; semantic memory writes skipped.", exc_info=True)
        return [None] * len(texts)

    results: list[Optional[list[float]]] = [None] * len(texts)
    for idx, vector in zip(non_empty_indices, vectors):
        results[idx] = vector.tolist()
    return results
