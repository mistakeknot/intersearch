"""Embedding client — shared across interject and tldr-swinton.

Loads sentence-transformers model locally (all-MiniLM-L6-v2, 384 dims).
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


class EmbeddingClient:
    """Text -> vector embeddings with lazy model loading."""

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.model_name = model_name
        self._model = None

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer

        logger.info("Loading embedding model: %s", self.model_name)
        self._model = SentenceTransformer(self.model_name)

    def embed(self, text: str) -> np.ndarray:
        """Embed a single text. Returns normalized vector."""
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        """Embed multiple texts. Returns (N, dim) normalized array."""
        self._ensure_model()
        embeddings = self._model.encode(
            texts, normalize_embeddings=True, show_progress_bar=False
        )
        return np.array(embeddings, dtype=np.float32)

    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Cosine similarity between two normalized vectors."""
        return float(np.dot(a, b))


def vector_to_bytes(vec: np.ndarray) -> bytes:
    """Serialize numpy vector to bytes for SQLite blob storage."""
    return vec.astype(np.float32).tobytes()


def bytes_to_vector(data: bytes) -> np.ndarray:
    """Deserialize bytes from SQLite back to numpy vector."""
    return np.frombuffer(data, dtype=np.float32)
