"""
Basic unit tests for the differ and parser modules.
Run with: python -m pytest tests/
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.differ import compute_diff, _token_diff


class TestComputeDiff:

    def test_identical_lines(self):
        lines = ["Hello world", "This is a test"]
        result = compute_diff(lines, lines)
        assert all(r["status"] == "unchanged" for r in result)

    def test_added_line(self):
        a = ["Line one"]
        b = ["Line one", "Line two"]
        result = compute_diff(a, b)
        statuses = [r["status"] for r in result]
        assert "added" in statuses

    def test_removed_line(self):
        a = ["Line one", "Line two"]
        b = ["Line one"]
        result = compute_diff(a, b)
        statuses = [r["status"] for r in result]
        assert "removed" in statuses

    def test_modified_line_has_tokens(self):
        a = ["The agreement ends on Dec 31."]
        b = ["The agreement ends on Jan 15."]
        result = compute_diff(a, b)
        assert result[0]["status"] == "modified"
        assert len(result[0]["tokens"]) > 0

    def test_empty_inputs(self):
        result = compute_diff([], [])
        assert result == []


class TestTokenDiff:

    def test_unchanged(self):
        tokens = _token_diff("same text", "same text")
        types = [t["type"] for t in tokens if t["text"].strip()]
        assert all(t == "unchanged" for t in types)

    def test_word_change(self):
        tokens = _token_diff("pay on Dec 31", "pay on Jan 15")
        token_types = {t["type"] for t in tokens}
        assert "removed" in token_types
        assert "added" in token_types
