"""
Tests for AOS Gateway — Complexity Triage
"""
from aos.gateway.triage import assess_complexity


class TestAssessComplexity:
    """Test prompt complexity classification."""

    def test_short_simple_prompt_returns_tiny(self):
        messages = [{"role": "user", "content": "Hello, how are you?"}]
        assert assess_complexity(messages) == "tiny"

    def test_long_prompt_over_1000_chars_returns_heavy(self):
        messages = [{"role": "user", "content": "x" * 1001}]
        assert assess_complexity(messages) == "heavy"

    def test_code_keyword_returns_heavy(self):
        messages = [{"role": "user", "content": "write code for a REST API"}]
        assert assess_complexity(messages) == "heavy"

    def test_analyze_keyword_returns_heavy(self):
        messages = [{"role": "user", "content": "analyze this dataset"}]
        assert assess_complexity(messages) == "heavy"

    def test_python_keyword_returns_heavy(self):
        messages = [{"role": "user", "content": "how does python work?"}]
        assert assess_complexity(messages) == "heavy"

    def test_debug_keyword_returns_heavy(self):
        messages = [{"role": "user", "content": "debug this function"}]
        assert assess_complexity(messages) == "heavy"

    def test_case_insensitive_keywords(self):
        messages = [{"role": "user", "content": "WRITE CODE for me"}]
        assert assess_complexity(messages) == "heavy"

    def test_empty_messages_returns_tiny(self):
        messages = []
        assert assess_complexity(messages) == "tiny"

    def test_non_string_content_skipped(self):
        messages = [{"role": "user", "content": None}, {"role": "user", "content": "hi"}]
        assert assess_complexity(messages) == "tiny"

    def test_multiple_messages_concatenated(self):
        messages = [
            {"role": "user", "content": "please"},
            {"role": "user", "content": "refactor this module"},
        ]
        assert assess_complexity(messages) == "heavy"
