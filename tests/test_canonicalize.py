"""Tests for jhcontext.canonicalize — URDNA2015 (with sorted-JSON fallback)."""

import json

import pytest

from jhcontext.canonicalize import (
    DETERMINISTIC_JSON,
    URDNA2015,
    algorithm,
    canonicalize,
)


@pytest.fixture
def jsonld_doc():
    """A minimal JSON-LD doc with @context — required for URDNA2015 to produce triples."""
    return {
        "@context": {
            "jh": "https://jhcontext.com/vocab#",
            "@vocab": "https://jhcontext.com/vocab#",
        },
        "@type": "jh:Envelope",
        "context_id": "ctx-test",
        "scope": "test",
    }


class TestAlgorithm:
    def test_reports_active_algorithm(self):
        assert algorithm() in (URDNA2015, DETERMINISTIC_JSON)

    def test_default_is_deterministic_json(self):
        """Without an explicit mode arg, env var, or override, default is fast path."""
        assert algorithm() == DETERMINISTIC_JSON

    def test_urdna2015_when_explicitly_requested(self):
        try:
            import pyld  # noqa: F401
        except ImportError:
            pytest.skip("pyld not installed")
        assert algorithm(URDNA2015) == URDNA2015


class TestCanonicalize:
    def test_deterministic(self, jsonld_doc):
        assert canonicalize(jsonld_doc) == canonicalize(jsonld_doc)

    def test_key_order_invariant(self):
        a = {
            "@context": {"@vocab": "https://jhcontext.com/vocab#"},
            "scope": "x",
            "context_id": "ctx-1",
        }
        b = {
            "@context": {"@vocab": "https://jhcontext.com/vocab#"},
            "context_id": "ctx-1",
            "scope": "x",
        }
        assert canonicalize(a) == canonicalize(b)

    def test_value_change_changes_output(self, jsonld_doc):
        before = canonicalize(jsonld_doc)
        jsonld_doc["scope"] = "tampered"
        assert canonicalize(jsonld_doc) != before

    def test_unicode_preserved(self):
        doc = {
            "@context": {"@vocab": "https://jhcontext.com/vocab#"},
            "name": "João",
        }
        out = canonicalize(doc)
        assert "João" in out or "Jo\\u00e3o" in out

    def test_returns_string(self, jsonld_doc):
        assert isinstance(canonicalize(jsonld_doc), str)


class TestDeterministicJsonFallback:
    def test_fallback_format(self, monkeypatch):
        """When pyld is unavailable the deterministic-JSON path runs."""
        import importlib

        canon_module = importlib.import_module("jhcontext.canonicalize")
        monkeypatch.setattr(canon_module, "_PYLD_AVAILABLE", False)
        monkeypatch.setattr(canon_module, "_jsonld", None)
        result = canon_module.canonicalize({"b": 2, "a": 1})
        assert result == '{"a":1,"b":2}'
        assert json.loads(result) == {"a": 1, "b": 2}
        assert canon_module.algorithm() == DETERMINISTIC_JSON
