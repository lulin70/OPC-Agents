"""LLM Response Cache — reduces API costs and latency via prompt deduplication."""

import hashlib
import json
import time
import logging
import threading
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Default TTL: 7 days (LLM models update infrequently)
DEFAULT_CACHE_TTL = 7 * 24 * 3600


class LLMCache:
    """SQLite-backed LLM response cache with TTL and hit tracking."""

    def __init__(self, db_path: str, ttl: int = DEFAULT_CACHE_TTL):
        self._db_path = db_path
        self._ttl = ttl
        self._lock = threading.RLock()
        self._ensure_table()

    def _ensure_table(self):
        """Create cache table if not exists."""
        import sqlite3

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS llm_cache (
                    cache_key TEXT PRIMARY KEY,
                    model TEXT NOT NULL,
                    temperature REAL NOT NULL,
                    max_tokens INTEGER NOT NULL,
                    system_prompt_hash TEXT NOT NULL DEFAULT '',
                    prompt_hash TEXT NOT NULL DEFAULT '',
                    response_content TEXT NOT NULL,
                    provider TEXT DEFAULT '',
                    hit_count INTEGER DEFAULT 0,
                    created_at REAL NOT NULL,
                    last_hit_at REAL,
                    expires_at REAL NOT NULL
                )
            """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_llm_cache_expires ON llm_cache(expires_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_llm_cache_model ON llm_cache(model)"
            )

    @staticmethod
    def compute_key(
        model: str,
        temperature: float,
        max_tokens: int,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Compute SHA256 cache key from LLM call parameters."""
        raw = f"{model}|{temperature}|{max_tokens}|{system_prompt}|{user_prompt}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(
        self,
        model: str,
        temperature: float,
        max_tokens: int,
        system_prompt: str,
        user_prompt: str,
    ) -> Optional[str]:
        """Look up cached response. Returns None if not found or expired."""
        key = self.compute_key(
            model, temperature, max_tokens, system_prompt, user_prompt
        )
        now = time.time()
        import sqlite3

        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                row = conn.execute(
                    "SELECT response_content, expires_at FROM llm_cache WHERE cache_key = ?",
                    (key,),
                ).fetchone()
                if row is None:
                    return None
                content, expires_at = row
                if now > expires_at:
                    conn.execute("DELETE FROM llm_cache WHERE cache_key = ?", (key,))
                    logger.debug("[LLMCache] Expired entry removed: %s...", key[:12])
                    return None
                conn.execute(
                    "UPDATE llm_cache SET hit_count = hit_count + 1, last_hit_at = ? WHERE cache_key = ?",
                    (now, key),
                )
                logger.debug("[LLMCache] Cache hit: %s...", key[:12])
                return content

    def put(
        self,
        model: str,
        temperature: float,
        max_tokens: int,
        system_prompt: str,
        user_prompt: str,
        response: str,
        provider: str = "",
    ) -> None:
        """Store LLM response in cache. Skip if temperature >= 0.7 (high variance)."""
        if temperature >= 0.7:
            logger.debug(
                "[LLMCache] Skip caching: temperature=%.1f >= 0.7", temperature
            )
            return
        key = self.compute_key(
            model, temperature, max_tokens, system_prompt, user_prompt
        )
        now = time.time()
        expires_at = now + self._ttl
        import sqlite3

        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO llm_cache
                    (cache_key, model, temperature, max_tokens, system_prompt_hash, prompt_hash,
                     response_content, provider, hit_count, created_at, last_hit_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, NULL, ?)
                """,
                    (
                        key,
                        model,
                        temperature,
                        max_tokens,
                        hashlib.sha256(system_prompt.encode()).hexdigest()[:16],
                        hashlib.sha256(user_prompt.encode()).hexdigest()[:16],
                        response,
                        provider,
                        now,
                        expires_at,
                    ),
                )
                logger.debug(
                    "[LLMCache] Cached response: %s... (TTL=%ds)", key[:12], self._ttl
                )

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count of removed entries."""
        now = time.time()
        import sqlite3

        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM llm_cache WHERE expires_at < ?", (now,)
                )
                count = cursor.rowcount
                if count > 0:
                    logger.info("[LLMCache] Cleaned up %d expired entries", count)
                return count

    def stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        import sqlite3

        with sqlite3.connect(self._db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM llm_cache").fetchone()[0]
            hits = (
                conn.execute("SELECT SUM(hit_count) FROM llm_cache").fetchone()[0] or 0
            )
            return {"total_entries": total, "total_hits": hits}


# Module-level singleton
_cache_instance: Optional[LLMCache] = None


def get_llm_cache() -> Optional[LLMCache]:
    """Get or create the LLM cache singleton."""
    global _cache_instance
    if _cache_instance is not None:
        return _cache_instance
    try:
        import os

        data_dir = os.environ.get(
            "OPC_DATA_DIR",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"),
        )
        os.makedirs(data_dir, exist_ok=True)
        db_path = os.path.join(data_dir, "opc_data.db")
        ttl = int(os.environ.get("OPC_LLM_CACHE_TTL", str(DEFAULT_CACHE_TTL)))
        _cache_instance = LLMCache(db_path, ttl=ttl)
        return _cache_instance
    except Exception as e:
        logger.warning("[LLMCache] Failed to initialize: %s", e)
        return None
