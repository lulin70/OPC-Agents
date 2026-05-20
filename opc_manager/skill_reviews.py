"""Skill Rating & Review System — user feedback for marketplace skills."""

import html
import uuid
import time
import logging
import threading
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class SkillReview:
    """A single user review for a skill."""

    review_id: str
    skill_id: str
    user_id: str
    rating: int  # 1-5 stars
    review_text: str = ""
    review_title: str = ""
    is_verified: bool = False
    helpful_count: int = 0
    status: str = "active"  # active/hidden/flagged
    created_at: float = 0.0
    updated_at: float = 0.0

    def __post_init__(self):
        if not self.review_id:
            self.review_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = time.time()
        if not self.updated_at:
            self.updated_at = self.created_at


class SkillReviewManager:
    """Manages skill reviews with SQLite persistence."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._lock = threading.RLock()
        self._ensure_table()

    def _ensure_table(self):
        import sqlite3

        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS skill_reviews (
                        review_id TEXT PRIMARY KEY,
                        skill_id TEXT NOT NULL,
                        user_id TEXT NOT NULL DEFAULT 'default',
                        rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
                        review_text TEXT DEFAULT '',
                        review_title TEXT DEFAULT '',
                        is_verified INTEGER DEFAULT 0,
                        helpful_count INTEGER DEFAULT 0,
                        status TEXT DEFAULT 'active' CHECK(status IN ('active','hidden','flagged')),
                        created_at REAL NOT NULL,
                        updated_at REAL
                    )
                """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_reviews_skill ON skill_reviews(skill_id)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_reviews_user ON skill_reviews(user_id)"
                )

    def add_review(
        self,
        skill_id: str,
        rating: int,
        review_text: str = "",
        review_title: str = "",
        user_id: str = "default",
    ) -> SkillReview:
        """Add a new review. Returns the created SkillReview."""
        if not skill_id or len(skill_id) > 100:
            raise ValueError("skill_id must be 1-100 characters")
        if not user_id or len(user_id) > 100:
            raise ValueError("user_id must be 1-100 characters")
        if not 1 <= rating <= 5:
            raise ValueError(f"Rating must be 1-5, got {rating}")
        review = SkillReview(
            review_id=str(uuid.uuid4()),
            skill_id=skill_id,
            user_id=user_id,
            rating=rating,
            review_text=html.escape(review_text[:500]),
            review_title=html.escape(review_title[:100]),
        )
        import sqlite3

        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO skill_reviews (review_id, skill_id, user_id, rating, review_text,
                        review_title, is_verified, helpful_count, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 0, 0, 'active', ?, ?)
                """,
                    (
                        review.review_id,
                        review.skill_id,
                        review.user_id,
                        review.rating,
                        review.review_text,
                        review.review_title,
                        review.created_at,
                        review.updated_at,
                    ),
                )
        self._update_skill_rating(skill_id)
        logger.info("[SkillReview] Added review for %s: %d stars", skill_id, rating)
        return review

    def get_reviews(
        self, skill_id: str, status: str = "active", limit: int = 20, offset: int = 0
    ) -> List[SkillReview]:
        """Get reviews for a skill, sorted by newest first."""
        import sqlite3

        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                rows = conn.execute(
                    """
                    SELECT review_id, skill_id, user_id, rating, review_text, review_title,
                           is_verified, helpful_count, status, created_at, updated_at
                    FROM skill_reviews
                    WHERE skill_id = ? AND status = ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """,
                    (skill_id, status, limit, offset),
                ).fetchall()
            return [SkillReview(*row) for row in rows]

    def get_average_rating(self, skill_id: str) -> float:
        """Get average rating for a skill."""
        import sqlite3

        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                row = conn.execute(
                    "SELECT AVG(rating) FROM skill_reviews WHERE skill_id = ? AND status = 'active'",
                    (skill_id,),
                ).fetchone()
                return round(row[0], 1) if row[0] else 0.0

    def get_review_count(self, skill_id: str) -> int:
        """Get total review count for a skill."""
        import sqlite3

        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                row = conn.execute(
                    "SELECT COUNT(*) FROM skill_reviews WHERE skill_id = ? AND status = 'active'",
                    (skill_id,),
                ).fetchone()
                return row[0]

    def mark_helpful(self, review_id: str) -> bool:
        """Increment helpful count for a review."""
        import sqlite3

        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute(
                    "UPDATE skill_reviews SET helpful_count = helpful_count + 1 WHERE review_id = ?",
                    (review_id,),
                )
                return cursor.rowcount > 0

    def delete_review(self, review_id: str) -> bool:
        """Soft-delete a review (set status='hidden')."""
        import sqlite3

        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                # Get skill_id before updating
                row = conn.execute(
                    "SELECT skill_id FROM skill_reviews WHERE review_id = ?",
                    (review_id,),
                ).fetchone()
                if not row:
                    return False
                skill_id = row[0]
                conn.execute(
                    "UPDATE skill_reviews SET status = 'hidden', updated_at = ? WHERE review_id = ?",
                    (time.time(), review_id),
                )
        self._update_skill_rating(skill_id)
        return True

    def _update_skill_rating(self, skill_id: str):
        """Update the rating column in external_skills table."""
        avg = self.get_average_rating(skill_id)
        import sqlite3

        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                try:
                    conn.execute(
                        "UPDATE external_skills SET rating = ? WHERE id = ?",
                        (avg, skill_id),
                    )
                except Exception as e:
                    logger.warning("[SkillReview] Failed to update skill rating: %s", e)

    def get_rating_summary(self, skill_id: str) -> Dict[str, Any]:
        """Get full rating summary for a skill."""
        import sqlite3

        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                # Average and count
                row = conn.execute(
                    """
                    SELECT AVG(rating), COUNT(*),
                           SUM(CASE WHEN rating=5 THEN 1 ELSE 0 END),
                           SUM(CASE WHEN rating=4 THEN 1 ELSE 0 END),
                           SUM(CASE WHEN rating=3 THEN 1 ELSE 0 END),
                           SUM(CASE WHEN rating=2 THEN 1 ELSE 0 END),
                           SUM(CASE WHEN rating=1 THEN 1 ELSE 0 END)
                    FROM skill_reviews WHERE skill_id = ? AND status = 'active'
                """,
                    (skill_id,),
                ).fetchone()
                avg, total, s5, s4, s3, s2, s1 = row
                return {
                    "average": round(avg, 1) if avg else 0.0,
                    "total": total or 0,
                    "distribution": {
                        5: s5 or 0,
                        4: s4 or 0,
                        3: s3 or 0,
                        2: s2 or 0,
                        1: s1 or 0,
                    },
                }

    def get_average_ratings(self, skill_ids: list) -> dict:
        """Get average ratings for multiple skills in one query."""
        if not skill_ids:
            return {}
        import sqlite3

        placeholders = ",".join("?" * len(skill_ids))
        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                rows = conn.execute(
                    f"""
                    SELECT skill_id, AVG(rating) as avg_rating
                    FROM skill_reviews
                    WHERE skill_id IN ({placeholders}) AND status = 'active'
                    GROUP BY skill_id
                """,
                    skill_ids,
                ).fetchall()
                return {row[0]: round(row[1], 1) for row in rows}


# Module-level singleton
_manager: Optional[SkillReviewManager] = None


def get_review_manager() -> Optional[SkillReviewManager]:
    """Get or create the SkillReviewManager singleton."""
    global _manager
    if _manager is not None:
        return _manager
    try:
        import os

        data_dir = os.environ.get(
            "OPC_DATA_DIR",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"),
        )
        os.makedirs(data_dir, exist_ok=True)
        db_path = os.path.join(data_dir, "opc_data.db")
        _manager = SkillReviewManager(db_path)
        return _manager
    except Exception as e:
        logger.warning("[SkillReview] Failed to initialize: %s", e)
        return None
