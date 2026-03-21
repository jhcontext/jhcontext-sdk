"""Tests for jhcontext.canonicalize — deterministic JSON serialization."""

from jhcontext.canonicalize import canonicalize


class TestCanonicalize:
    def test_sorted_keys(self):
        result = canonicalize({"b": 2, "a": 1})
        assert result == '{"a":1,"b":2}'

    def test_no_spaces(self):
        result = canonicalize({"key": "value"})
        assert " " not in result

    def test_nested_sorted(self):
        result = canonicalize({"z": {"b": 2, "a": 1}, "a": 0})
        assert result == '{"a":0,"z":{"a":1,"b":2}}'

    def test_deterministic(self):
        obj = {"x": [1, 2, 3], "a": "hello"}
        assert canonicalize(obj) == canonicalize(obj)

    def test_unicode(self):
        result = canonicalize({"name": "João"})
        assert "João" in result

    def test_empty_dict(self):
        assert canonicalize({}) == "{}"
