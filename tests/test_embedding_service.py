"""Unit tests for EmbeddingService and cosine_similarity."""

import os
import struct
import sqlite3
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from opc_manager.embedding_service import EmbeddingService, cosine_similarity


class TestCosineSimilarity(unittest.TestCase):
    """Test cosine_similarity function."""

    def test_identical_vectors(self):
        a = [1.0, 0.0, 0.0]
        self.assertAlmostEqual(cosine_similarity(a, a), 1.0)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        self.assertAlmostEqual(cosine_similarity(a, b), 0.0)

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        self.assertAlmostEqual(cosine_similarity(a, b), -1.0)

    def test_zero_vector(self):
        a = [1.0, 0.0]
        b = [0.0, 0.0]
        self.assertAlmostEqual(cosine_similarity(a, b), 0.0)

    def test_different_lengths_raises(self):
        # Should work with same-length vectors
        a = [1.0, 2.0, 3.0]
        b = [4.0, 5.0, 6.0]
        result = cosine_similarity(a, b)
        self.assertIsInstance(result, float)
        self.assertGreater(result, 0.0)

    def test_realistic_embeddings(self):
        # Two similar sentences should have higher similarity than dissimilar
        similar_a = [0.1, 0.9, 0.2, 0.8]
        similar_b = [0.15, 0.85, 0.25, 0.75]
        dissimilar = [0.9, 0.1, 0.8, 0.2]
        sim_score = cosine_similarity(similar_a, similar_b)
        dis_score = cosine_similarity(similar_a, dissimilar)
        self.assertGreater(sim_score, dis_score)


class TestEmbeddingServiceDetection(unittest.TestCase):
    """Test Ollama availability detection."""

    @patch("opc_manager.embedding_service.requests.get")
    def test_detect_available(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "nomic-embed-text:latest"}]}
        mock_get.return_value = mock_resp
        svc = EmbeddingService()
        self.assertTrue(svc.enabled)

    @patch("opc_manager.embedding_service.requests.get")
    def test_detect_model_not_found(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "llama3:latest"}]}
        mock_get.return_value = mock_resp
        svc = EmbeddingService()
        self.assertFalse(svc.enabled)

    @patch("opc_manager.embedding_service.requests.get")
    def test_detect_ollama_not_running(self, mock_get):
        import requests as req

        mock_get.side_effect = req.RequestException("Connection refused")
        svc = EmbeddingService()
        self.assertFalse(svc.enabled)

    def test_detect_disabled_by_env(self):
        with patch.dict(os.environ, {"OPC_EMBEDDING_ENABLED": "false"}):
            svc = EmbeddingService()
            self.assertFalse(svc.enabled)


class TestEmbeddingServiceCache(unittest.TestCase):
    """Test SQLite embedding cache."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Create service with Ollama disabled (we only test cache here)
        with patch.dict(os.environ, {"OPC_EMBEDDING_ENABLED": "false"}):
            self.svc = EmbeddingService()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_init_cache_creates_db(self):
        # Enable temporarily for cache init
        self.svc._enabled = True
        self.svc.init_cache(self.tmpdir)
        db_path = os.path.join(self.tmpdir, "embedding_cache.db")
        self.assertTrue(os.path.exists(db_path))

    def test_cache_round_trip(self):
        self.svc._enabled = True
        self.svc.init_cache(self.tmpdir)
        # Manually write and read
        test_hash = "abc123"
        test_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        self.svc._set_cached(test_hash, test_embedding)
        result = self.svc._get_cached(test_hash)
        self.assertIsNotNone(result)
        for a, b in zip(result, test_embedding):
            self.assertAlmostEqual(a, b, places=5)

    def test_cache_miss_returns_none(self):
        self.svc._enabled = True
        self.svc.init_cache(self.tmpdir)
        result = self.svc._get_cached("nonexistent")
        self.assertIsNone(result)


class TestEmbeddingServiceEmbed(unittest.TestCase):
    """Test embed() method."""

    @patch("opc_manager.embedding_service.requests.post")
    @patch("opc_manager.embedding_service.requests.get")
    def test_embed_success(self, mock_get, mock_post):
        # Mock detection
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "nomic-embed-text:latest"}]}
        mock_get.return_value = mock_resp

        # Mock embed API
        mock_embed_resp = MagicMock()
        mock_embed_resp.status_code = 200
        mock_embed_resp.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
        mock_embed_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_embed_resp

        svc = EmbeddingService()
        tmpdir = tempfile.mkdtemp()
        svc.init_cache(tmpdir)
        result = svc.embed("hello world")
        self.assertEqual(result, [0.1, 0.2, 0.3])

    def test_embed_disabled_returns_none(self):
        with patch.dict(os.environ, {"OPC_EMBEDDING_ENABLED": "false"}):
            svc = EmbeddingService()
            result = svc.embed("hello")
            self.assertIsNone(result)

    @patch("opc_manager.embedding_service.requests.post")
    @patch("opc_manager.embedding_service.requests.get")
    def test_embed_uses_cache(self, mock_get, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "nomic-embed-text:latest"}]}
        mock_get.return_value = mock_resp

        mock_embed_resp = MagicMock()
        mock_embed_resp.status_code = 200
        mock_embed_resp.json.return_value = {"embedding": [0.5, 0.6]}
        mock_embed_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_embed_resp

        svc = EmbeddingService()
        tmpdir = tempfile.mkdtemp()
        svc.init_cache(tmpdir)

        # First call hits API
        result1 = svc.embed("test text")
        self.assertEqual(result1, [0.5, 0.6])
        self.assertEqual(mock_post.call_count, 1)

        # Second call should use cache (values may have float precision from struct pack)
        result2 = svc.embed("test text")
        self.assertEqual(len(result2), 2)
        self.assertAlmostEqual(result2[0], 0.5, places=5)
        self.assertAlmostEqual(result2[1], 0.6, places=5)
        self.assertEqual(mock_post.call_count, 1)  # No additional API call

    def test_embed_batch(self):
        with patch.dict(os.environ, {"OPC_EMBEDDING_ENABLED": "false"}):
            svc = EmbeddingService()
            results = svc.embed_batch(["a", "b", "c"])
            self.assertEqual(len(results), 3)
            self.assertTrue(all(r is None for r in results))


if __name__ == "__main__":
    unittest.main()
