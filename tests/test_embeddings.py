"""Tests for shared embedding client."""

import numpy as np
import pytest

from intersearch.embeddings import (
    EMBEDDING_DIM,
    EmbeddingClient,
    bytes_to_vector,
    vector_to_bytes,
)


class TestEmbeddingClient:
    def test_embed_returns_correct_dim(self):
        client = EmbeddingClient()
        vec = client.embed("test text")
        assert vec.shape == (EMBEDDING_DIM,)

    def test_embed_normalized(self):
        client = EmbeddingClient()
        vec = client.embed("test text")
        norm = np.linalg.norm(vec)
        assert abs(norm - 1.0) < 0.01

    def test_embed_batch(self):
        client = EmbeddingClient()
        vecs = client.embed_batch(["hello", "world"])
        assert vecs.shape == (2, EMBEDDING_DIM)

    def test_cosine_similarity_identical(self):
        client = EmbeddingClient()
        vec = client.embed("same text")
        sim = client.cosine_similarity(vec, vec)
        assert abs(sim - 1.0) < 0.01

    def test_cosine_similarity_different(self):
        client = EmbeddingClient()
        a = client.embed("quantum physics research")
        b = client.embed("chocolate cake recipe")
        sim = client.cosine_similarity(a, b)
        assert sim < 0.8


class TestSerialization:
    def test_roundtrip(self):
        vec = np.random.randn(EMBEDDING_DIM).astype(np.float32)
        data = vector_to_bytes(vec)
        recovered = bytes_to_vector(data)
        np.testing.assert_array_almost_equal(vec, recovered)
