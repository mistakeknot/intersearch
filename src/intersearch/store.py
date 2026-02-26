"""Embedding persistence — per-project SQLite vector storage with incremental indexing.

Adapted from intercache's embeddings.py. This is the canonical location for
embedding persistence in the Interverse ecosystem.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .embeddings import EmbeddingClient, vector_to_bytes, bytes_to_vector, DEFAULT_MODEL

logger = logging.getLogger(__name__)

DEFAULT_STORE_DIR = Path.home() / ".intersearch"

SCHEMA = """
CREATE TABLE IF NOT EXISTS embeddings (
    path TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL,
    model TEXT NOT NULL,
    vector BLOB NOT NULL,
    updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_embeddings_sha256 ON embeddings(sha256);
"""


def _project_hash(project_root: str) -> str:
    """Deterministic short hash for a project root path."""
    return hashlib.sha256(project_root.encode()).hexdigest()[:12]


class EmbeddingStore:
    """Per-project embedding storage with lazy model loading."""

    def __init__(
        self,
        project_root: str,
        store_dir: Path | None = None,
        model_name: str = DEFAULT_MODEL,
    ):
        self.project_root = project_root
        self.model_name = model_name
        base = (store_dir or DEFAULT_STORE_DIR) / "index" / _project_hash(project_root)
        base.mkdir(parents=True, exist_ok=True)
        self.db_path = base / "embeddings.db"
        self._conn: sqlite3.Connection | None = None
        self._embedder: EmbeddingClient | None = None

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._conn.executescript(SCHEMA)
            self._check_model_version()
        return self._conn

    def _check_model_version(self) -> None:
        """Invalidate all embeddings if model version changed."""
        conn = self._conn
        row = conn.execute(
            "SELECT value FROM meta WHERE key = 'model_name'"
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO meta (key, value) VALUES ('model_name', ?)",
                (self.model_name,),
            )
            conn.commit()
        elif row[0] != self.model_name:
            logger.warning(
                "Embedding model changed (%s -> %s), invalidating all embeddings",
                row[0],
                self.model_name,
            )
            conn.execute("DELETE FROM embeddings")
            conn.execute(
                "UPDATE meta SET value = ? WHERE key = 'model_name'",
                (self.model_name,),
            )
            conn.commit()

    def _ensure_embedder(self) -> EmbeddingClient:
        if self._embedder is None:
            self._embedder = EmbeddingClient(self.model_name)
        return self._embedder

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def index_file(self, path: str, content: str, sha256: str) -> bool:
        """Index a file's content. Returns True if newly indexed, False if up-to-date."""
        conn = self._connect()
        row = conn.execute(
            "SELECT sha256 FROM embeddings WHERE path = ?", (path,)
        ).fetchone()

        if row and row[0] == sha256:
            return False

        embedder = self._ensure_embedder()
        vec = embedder.embed(content)
        now = datetime.now(timezone.utc).isoformat()

        conn.execute(
            "INSERT INTO embeddings (path, sha256, model, vector, updated) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(path) DO UPDATE SET sha256=?, model=?, vector=?, updated=?",
            (
                path, sha256, self.model_name, vector_to_bytes(vec), now,
                sha256, self.model_name, vector_to_bytes(vec), now,
            ),
        )
        conn.commit()
        return True

    def query(self, query_text: str, top_k: int = 10) -> list[dict]:
        """Semantic search: return top-K files by cosine similarity.

        Returns [{path, sha256, score, updated}, ...] sorted by score descending.
        """
        conn = self._connect()
        embedder = self._ensure_embedder()
        query_vec = embedder.embed(query_text)

        rows = conn.execute(
            "SELECT path, sha256, vector, updated FROM embeddings"
        ).fetchall()

        if not rows:
            return []

        results = []
        for path, sha256, vec_bytes, updated in rows:
            vec = bytes_to_vector(vec_bytes)
            score = float(np.dot(query_vec, vec))
            results.append({
                "path": path,
                "sha256": sha256,
                "score": score,
                "updated": updated,
            })

        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]

    def invalidate(self, path: str) -> bool:
        """Remove embedding for a path. Returns True if it existed."""
        conn = self._connect()
        cursor = conn.execute("DELETE FROM embeddings WHERE path = ?", (path,))
        conn.commit()
        return cursor.rowcount > 0

    def count(self) -> int:
        """Return total number of indexed files."""
        conn = self._connect()
        row = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()
        return row[0]

    def stale_paths(self, entries: list[dict]) -> list[str]:
        """Return paths whose sha256 differs between store and provided entries."""
        conn = self._connect()
        stale = []
        for entry in entries:
            row = conn.execute(
                "SELECT sha256 FROM embeddings WHERE path = ?", (entry["path"],)
            ).fetchone()
            if row is None or row[0] != entry["sha256"]:
                stale.append(entry["path"])
        return stale
