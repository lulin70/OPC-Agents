"""Skill Review System Unit Tests.

Covers:
- add_review: creates review, persists to DB, updates skill rating
- add_review_invalid_rating: rejects ratings outside 1-5
- get_reviews: returns reviews sorted newest-first, respects status filter
- get_average_rating: computes correct average for active reviews
- get_review_count: counts only active reviews
- mark_helpful: increments helpful_count
- delete_review_soft: sets status to hidden, recalculates rating
- rating_summary: returns average, total, and star distribution
- review_text_truncation: review_text capped at 500, review_title at 100

Run command:
    pytest tests/test_skill_reviews.py -v --tb=short
"""

import pytest

from opc_manager.skill_reviews import SkillReviewManager


@pytest.fixture
def db_path(tmp_path):
    """Provide a temporary database path for each test."""
    return str(tmp_path / "test_reviews.db")


@pytest.fixture
def manager(db_path):
    """Provide a fresh SkillReviewManager for each test."""
    return SkillReviewManager(db_path)


class TestAddReview:
    """Test suite for adding reviews."""

    def test_add_review(self, manager):
        """Adding a review returns a SkillReview with correct fields."""
        review = manager.add_review("skill-1", 5, "Great!", "Title", "user-1")
        assert review.skill_id == "skill-1"
        assert review.rating == 5
        assert review.review_text == "Great!"
        assert review.review_title == "Title"
        assert review.user_id == "user-1"
        assert review.status == "active"
        assert review.created_at > 0

    def test_add_review_default_user(self, manager):
        """Default user_id is 'default' when not specified."""
        review = manager.add_review("skill-1", 4)
        assert review.user_id == "default"

    def test_add_review_invalid_rating(self, manager):
        """Ratings outside 1-5 raise ValueError."""
        with pytest.raises(ValueError, match="Rating must be 1-5"):
            manager.add_review("skill-1", 0)
        with pytest.raises(ValueError, match="Rating must be 1-5"):
            manager.add_review("skill-1", 6)


class TestGetReviews:
    """Test suite for retrieving reviews."""

    def test_get_reviews(self, manager):
        """get_reviews returns reviews sorted newest first."""
        import time

        manager.add_review("skill-1", 5, "First")
        time.sleep(0.01)
        r2 = manager.add_review("skill-1", 3, "Second")
        reviews = manager.get_reviews("skill-1")
        assert len(reviews) == 2
        assert reviews[0].review_id == r2.review_id  # newest first

    def test_get_reviews_filters_by_status(self, manager):
        """get_reviews only returns reviews matching the given status."""
        manager.add_review("skill-1", 5, "Active review")
        reviews = manager.get_reviews("skill-1", status="active")
        assert len(reviews) == 1
        hidden = manager.get_reviews("skill-1", status="hidden")
        assert len(hidden) == 0

    def test_get_reviews_limit_offset(self, manager):
        """Pagination via limit and offset works correctly."""
        for i in range(5):
            manager.add_review("skill-1", i + 1, f"Review {i}")
        page1 = manager.get_reviews("skill-1", limit=2, offset=0)
        page2 = manager.get_reviews("skill-1", limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2
        assert page1[0].review_id != page2[0].review_id


class TestGetAverageRating:
    """Test suite for average rating calculation."""

    def test_get_average_rating(self, manager):
        """Average rating is correctly computed for active reviews."""
        manager.add_review("skill-1", 5)
        manager.add_review("skill-1", 3)
        assert manager.get_average_rating("skill-1") == 4.0

    def test_get_average_rating_no_reviews(self, manager):
        """Average rating is 0.0 when no reviews exist."""
        assert manager.get_average_rating("nonexistent") == 0.0


class TestGetReviewCount:
    """Test suite for review count."""

    def test_get_review_count(self, manager):
        """Review count reflects only active reviews."""
        manager.add_review("skill-1", 5)
        manager.add_review("skill-1", 4)
        assert manager.get_review_count("skill-1") == 2

    def test_get_review_count_excludes_hidden(self, manager):
        """Hidden reviews are excluded from count."""
        review = manager.add_review("skill-1", 5)
        manager.delete_review(review.review_id)
        assert manager.get_review_count("skill-1") == 0


class TestMarkHelpful:
    """Test suite for marking reviews as helpful."""

    def test_mark_helpful(self, manager):
        """mark_helpful increments the helpful_count."""
        review = manager.add_review("skill-1", 5, "Nice")
        result = manager.mark_helpful(review.review_id)
        assert result is True
        reviews = manager.get_reviews("skill-1")
        assert reviews[0].helpful_count == 1

    def test_mark_helpful_nonexistent(self, manager):
        """mark_helpful returns False for nonexistent review."""
        result = manager.mark_helpful("nonexistent-id")
        assert result is False


class TestDeleteReview:
    """Test suite for soft-deleting reviews."""

    def test_delete_review_soft(self, manager):
        """delete_review soft-deletes (status=hidden) and recalculates rating."""
        manager.add_review("skill-1", 5)
        review2 = manager.add_review("skill-1", 1)
        assert manager.get_review_count("skill-1") == 2
        assert manager.get_average_rating("skill-1") == 3.0

        manager.delete_review(review2.review_id)
        assert manager.get_review_count("skill-1") == 1
        assert manager.get_average_rating("skill-1") == 5.0

    def test_delete_review_nonexistent(self, manager):
        """delete_review returns False for nonexistent review."""
        assert manager.delete_review("nonexistent-id") is False


class TestRatingSummary:
    """Test suite for rating summary."""

    def test_rating_summary(self, manager):
        """rating_summary returns correct average, total, and distribution."""
        manager.add_review("skill-1", 5)
        manager.add_review("skill-1", 5)
        manager.add_review("skill-1", 3)
        summary = manager.get_rating_summary("skill-1")
        assert summary["average"] == 4.3
        assert summary["total"] == 3
        assert summary["distribution"][5] == 2
        assert summary["distribution"][3] == 1
        assert summary["distribution"][4] == 0

    def test_rating_summary_no_reviews(self, manager):
        """rating_summary returns zeros when no reviews exist."""
        summary = manager.get_rating_summary("nonexistent")
        assert summary["average"] == 0.0
        assert summary["total"] == 0
        assert all(v == 0 for v in summary["distribution"].values())


class TestReviewTextTruncation:
    """Test suite for review text truncation."""

    def test_review_text_truncation(self, manager):
        """Review text is truncated to 500 chars and title to 100 chars."""
        long_text = "x" * 600
        long_title = "t" * 150
        review = manager.add_review("skill-1", 4, long_text, long_title)
        assert len(review.review_text) == 500
        assert len(review.review_title) == 100

        # Verify persisted values are also truncated
        reviews = manager.get_reviews("skill-1")
        assert len(reviews[0].review_text) == 500
        assert len(reviews[0].review_title) == 100
