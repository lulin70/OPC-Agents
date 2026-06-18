"""EmbeddingService — Ollama-based embedding generation for semantic search.

Uses local Ollama instance for zero-cost, privacy-preserving embeddings.
Gracefully degrades to None when Ollama is unavailable.

Configuration:
    OPC_EMBEDDING_MODEL — Ollama model name (default: nomic-embed-text)
    OPC_EMBEDDING_BASE_URL — Ollama API URL (default: http://localhost:11434)
    OPC_EMBEDDING_ENABLED — Enable/disable semantic search (default: auto-detect)
"""

import logging
import os
import sqlite3
import hashlib
from typing import List, Optional

import requests

from opc_manager.config import LLM_PROVIDERS

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"
DEFAULT_OLLAMA_URL = LLM_PROVIDERS["ollama"]
EMBEDDING_CACHE_DB = "embedding_cache.db"


class EmbeddingService:
    """Ollama-based embedding service with SQLite cache."""

    def __init__(self):
        self._model = os.environ.get("OPC_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
        self._base_url = os.environ.get("OPC_EMBEDDING_BASE_URL", DEFAULT_OLLAMA_URL)
        self._enabled = self._detect_availability()
        self._cache_db: Optional[str] = None

    def _detect_availability(self) -> bool:
        """Check if Ollama is running and the embedding model is available."""
        env_setting = os.environ.get("OPC_EMBEDDING_ENABLED", "").lower()
        if env_setting in ("false", "0", "no"):
            logger.info("[EmbeddingService] Disabled by OPC_EMBEDDING_ENABLED")
            return False

        try:
            resp = requests.get(f"{self._base_url}/api/tags", timeout=3)
            if resp.status_code != 200:
                return False
            models = [m.get("name", "") for m in resp.json().get("models", [])]
            # Check if any model name contains our embedding model
            available = any(self._model in m for m in models)
            if not available:
                logger.info(
                    "[EmbeddingService] Model '%s' not found. Available: %s. "
                    "Run: ollama pull %s",
                    self._model,
                    ", ".join(models) or "(none)",
                    self._model,
                )
                return False
            logger.info(
                "[EmbeddingService] Ollama embedding available: %s", self._model
            )
            return True
        except requests.RequestException:
            logger.info(
                "[EmbeddingService] Ollama not available, using keyword-only search"
            )
            return False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def init_cache(self, cache_dir: str) -> None:
        """Initialize the SQLite embedding cache database."""
        if not self._enabled:
            return
        self._cache_db = os.path.join(cache_dir, EMBEDDING_CACHE_DB)
        try:
            conn = sqlite3.connect(self._cache_db)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    content_hash TEXT PRIMARY KEY,
                    model TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.warning("[EmbeddingService] Cache init failed: %s", e)
            self._cache_db = None

    def _content_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _get_cached(self, content_hash: str) -> Optional[List[float]]:
        """Retrieve embedding from cache."""
        if not self._cache_db:
            return None
        try:
            conn = sqlite3.connect(self._cache_db)
            row = conn.execute(
                "SELECT embedding FROM embeddings WHERE content_hash=? AND model=?",
                (content_hash, self._model),
            ).fetchone()
            conn.close()
            if row:
                import struct

                data = row[0]
                return list(struct.unpack(f"<{len(data)//4}f", data))
        except Exception:
            pass
        return None

    def _set_cached(self, content_hash: str, embedding: List[float]) -> None:
        """Store embedding in cache."""
        if not self._cache_db:
            return
        try:
            import struct
            import time

            blob = struct.pack(f"<{len(embedding)}f", *embedding)
            conn = sqlite3.connect(self._cache_db)
            conn.execute(
                "INSERT OR REPLACE INTO embeddings (content_hash, model, embedding, created_at) VALUES (?, ?, ?, ?)",
                (content_hash, self._model, blob, time.time()),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("[EmbeddingService] Cache write failed: %s", e)

    def cleanup_old_entries(self, max_age_days: int = 30) -> int:
        """Remove cache entries older than max_age_days.

        Returns number of entries removed.
        """
        if not self._cache_db:
            return 0
        try:
            import time

            cutoff = time.time() - max_age_days * 86400
            conn = sqlite3.connect(self._cache_db)
            cursor = conn.execute(
                "DELETE FROM embeddings WHERE created_at < ?", (cutoff,)
            )
            removed = cursor.rowcount
            conn.commit()
            conn.close()
            if removed > 0:
                logger.info(
                    "[EmbeddingService] Cleaned up %d old cache entries", removed
                )
            return removed
        except Exception as e:
            logger.warning("[EmbeddingService] Cache cleanup failed: %s", e)
            return 0

    def embed(self, text: str) -> Optional[List[float]]:
        """Generate embedding for text using Ollama."""
        if not self._enabled:
            return None

        # Truncate long text for embedding
        text_to_embed = text[:2000] if len(text) > 2000 else text
        content_hash = self._content_hash(text_to_embed)

        # Check cache first
        cached = self._get_cached(content_hash)
        if cached is not None:
            return cached

        try:
            resp = requests.post(
                f"{self._base_url}/api/embeddings",
                json={"model": self._model, "prompt": text_to_embed},
                timeout=30,
            )
            resp.raise_for_status()
            embedding = resp.json().get("embedding")
            if embedding and len(embedding) > 0:
                self._set_cached(content_hash, embedding)
                return embedding
        except requests.RequestException as e:
            logger.warning("[EmbeddingService] Embedding failed: %s", e)
        return None

    def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Generate embeddings for multiple texts."""
        return [self.embed(t) for t in texts]


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
