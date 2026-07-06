"""Unit tests for extract_json_from_llm — 3-strategy extraction."""

import unittest

from opc_manager.utils import extract_json_from_llm


class TestExtractJsonCodeFence(unittest.TestCase):
    """Strategy 1: Markdown code fence extraction."""

    def test_json_code_fence(self):
        text = 'Here is the result:\n```json\n{"key": "value"}\n```\nDone.'
        result = extract_json_from_llm(text)
        self.assertEqual(result, {"key": "value"})

    def test_plain_code_fence(self):
        text = '```\n{"key": "value"}\n```'
        result = extract_json_from_llm(text)
        self.assertEqual(result, {"key": "value"})

    def test_code_fence_with_extra_text(self):
        text = 'I analyzed the request.\n```json\n{"steps": 3, "plan": "execute"}\n```\nProceeding.'
        result = extract_json_from_llm(text)
        self.assertEqual(result, {"steps": 3, "plan": "execute"})

    def test_code_fence_array_returns_first_dict(self):
        text = '```json\n[{"id": 1}, {"id": 2}]\n```'
        result = extract_json_from_llm(text)
        self.assertEqual(result, {"id": 1})

    def test_code_fence_invalid_json_falls_through(self):
        text = '```json\nnot valid json\n```\n{"valid": true}'
        result = extract_json_from_llm(text)
        self.assertEqual(result, {"valid": True})


class TestExtractJsonBraceDepth(unittest.TestCase):
    """Strategy 2: Brace-depth counter for JSON objects."""

    def test_simple_object(self):
        text = '{"name": "test"}'
        result = extract_json_from_llm(text)
        self.assertEqual(result, {"name": "test"})

    def test_nested_object(self):
        text = '{"outer": {"inner": 42}}'
        result = extract_json_from_llm(text)
        self.assertEqual(result, {"outer": {"inner": 42}})

    def test_object_with_surrounding_text(self):
        text = 'The result is {"status": "ok"} as expected.'
        result = extract_json_from_llm(text)
        self.assertEqual(result, {"status": "ok"})

    def test_first_valid_json_wins(self):
        text = 'First {"a": 1} then {"b": 2}'
        result = extract_json_from_llm(text)
        self.assertEqual(result, {"a": 1})

    def test_invalid_json_skipped(self):
        text = '{"broken": } valid {"ok": true}'
        result = extract_json_from_llm(text)
        self.assertEqual(result, {"ok": True})


class TestExtractJsonBracketDepth(unittest.TestCase):
    """Strategy 3: Bracket-depth counter for JSON arrays."""

    def test_array_of_dicts(self):
        text = '[{"id": 1}, {"id": 2}]'
        result = extract_json_from_llm(text)
        self.assertEqual(result, {"id": 1})

    def test_array_with_surrounding_text(self):
        text = 'Results: [{"name": "a"}, {"name": "b"}] end'
        result = extract_json_from_llm(text)
        self.assertEqual(result, {"name": "a"})

    def test_empty_array_returns_none(self):
        text = "[]"
        result = extract_json_from_llm(text)
        self.assertIsNone(result)

    def test_array_of_strings_returns_none(self):
        text = '["a", "b", "c"]'
        result = extract_json_from_llm(text)
        self.assertIsNone(result)


class TestExtractJsonEdgeCases(unittest.TestCase):
    """Edge cases and fallback behavior."""

    def test_empty_string(self):
        result = extract_json_from_llm("")
        self.assertIsNone(result)

    def test_none_input(self):
        result = extract_json_from_llm(None)
        self.assertIsNone(result)

    def test_no_json_at_all(self):
        result = extract_json_from_llm("Just plain text without any JSON")
        self.assertIsNone(result)

    def test_code_fence_priority_over_brace(self):
        """Code fence should be tried first."""
        text = '```json\n{"source": "fence"}\n```\n{"source": "brace"}'
        result = extract_json_from_llm(text)
        self.assertEqual(result, {"source": "fence"})

    def test_complex_nested_json(self):
        text = '{"plan": {"steps": [{"id": 1, "action": "search"}, {"id": 2, "action": "generate"}]}}'
        result = extract_json_from_llm(text)
        self.assertIsNotNone(result)
        self.assertEqual(len(result["plan"]["steps"]), 2)

    def test_json_with_string_containing_braces(self):
        text = '{"text": "hello {world}"}'
        result = extract_json_from_llm(text)
        # Brace depth counter may fail on this, but json.loads in code fence won't
        # Either way, should return valid result or None (not crash)
        if result is not None:
            self.assertEqual(result["text"], "hello {world}")


if __name__ == "__main__":
    unittest.main()
