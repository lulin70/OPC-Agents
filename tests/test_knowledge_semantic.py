"""Unit tests for KnowledgeBridge semantic search and degradation."""

import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from opc_manager.knowledge_bridge import (
    KnowledgeBridge,
    LocalFolderAdapter,
    KnowledgeEntry,
)


class TestLocalFolderKeywordFallback(unittest.TestCase):
    """Test keyword-only search when Ollama is unavailable."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Create test markdown files
        with open(os.path.join(self.tmpdir, "marketing.md"), "w") as f:
            f.write(
                "# Marketing Strategy\n\nWe need to focus on digital marketing channels.\n#marketing #strategy"
            )
        with open(os.path.join(self.tmpdir, "tech.md"), "w") as f:
            f.write(
                "# Technical Architecture\n\nThe system uses microservices.\n#tech #architecture"
            )
        with open(os.path.join(self.tmpdir, "notes.txt"), "w") as f:
            f.write("Random notes about nothing specific.")

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch.dict(os.environ, {"OPC_EMBEDDING_ENABLED": "false"})
    def test_keyword_search_finds_match(self):
        adapter = LocalFolderAdapter(self.tmpdir)
        results = adapter.search("marketing")
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0].title, "marketing")

    @patch.dict(os.environ, {"OPC_EMBEDDING_ENABLED": "false"})
    def test_keyword_search_no_match(self):
        adapter = LocalFolderAdapter(self.tmpdir)
        results = adapter.search("quantum physics")
        self.assertEqual(len(results), 0)

    @patch.dict(os.environ, {"OPC_EMBEDDING_ENABLED": "false"})
    def test_keyword_search_tag_match(self):
        adapter = LocalFolderAdapter(self.tmpdir)
        results = adapter.search("strategy")
        self.assertTrue(len(results) > 0)

    @patch.dict(os.environ, {"OPC_EMBEDDING_ENABLED": "false"})
    def test_max_results_limit(self):
        adapter = LocalFolderAdapter(self.tmpdir)
        results = adapter.search("a")  # matches content in multiple files
        for r in results:
            self.assertIsInstance(r, KnowledgeEntry)
        self.assertLessEqual(len(results), 5)


class TestLocalFolderSemanticSearch(unittest.TestCase):
    """Test semantic search when Ollama is available."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        with open(os.path.join(self.tmpdir, "sales.md"), "w") as f:
            f.write(
                "# Sales Revenue\n\nQuarterly revenue exceeded expectations.\n#sales #revenue"
            )
        with open(os.path.join(self.tmpdir, "dev.md"), "w") as f:
            f.write(
                "# Development Sprint\n\nCompleted all planned features.\n#dev #sprint"
            )

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("opc_manager.embedding_service.requests.get")
    @patch("opc_manager.embedding_service.requests.post")
    def test_semantic_search_with_mock_ollama(self, mock_post, mock_get):
        """Test that semantic scoring works when Ollama returns embeddings."""
        # Mock detection
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "nomic-embed-text:latest"}]}
        mock_get.return_value = mock_resp

        # Mock embeddings - sales doc gets higher similarity to "revenue" query
        call_count = [0]

        def mock_embed_side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_r = MagicMock()
            mock_r.status_code = 200
            mock_r.raise_for_status = MagicMock()
            # Return different embeddings for different texts
            if call_count[0] <= 2:  # Index building (2 docs)
                mock_r.json.return_value = {"embedding": [0.1] * 8}
            else:  # Query embedding
                mock_r.json.return_value = {"embedding": [0.9] * 8}
            return mock_r

        mock_post.side_effect = mock_embed_side_effect

        adapter = LocalFolderAdapter(self.tmpdir)
        results = adapter.search("revenue")
        self.assertTrue(len(results) > 0)
        # All results should have relevance_score > 0
        for r in results:
            self.assertGreater(r.relevance_score, 0.0)


class TestKnowledgeBridgeIntegration(unittest.TestCase):
    """Test KnowledgeBridge with semantic search."""

    @patch.dict(os.environ, {"OPC_KB_ENABLED": "false"})
    def test_disabled_returns_empty(self):
        kb = KnowledgeBridge()
        self.assertFalse(kb.enabled)
        self.assertEqual(kb.search("test"), [])

    @patch.dict(
        os.environ,
        {
            "OPC_KB_ENABLED": "true",
            "OPC_KB_TYPE": "local",
            "OPC_KB_PATH": "/nonexistent",
            "OPC_EMBEDDING_ENABLED": "false",
        },
    )
    def test_nonexistent_path(self):
        kb = KnowledgeBridge()
        # Should still initialize but with empty results
        results = kb.search("test")
        self.assertIsInstance(results, list)


if __name__ == "__main__":
    unittest.main()
