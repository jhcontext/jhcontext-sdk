"""Tests for jhcontext.semantics — UserML helpers."""

from jhcontext.semantics import (
    observation,
    interpretation,
    situation,
    userml_payload,
    sample_smart_office,
)


class TestObservation:
    def test_basic(self):
        obs = observation("user:alice", "temperature", 22.3)
        assert obs["subject"] == "user:alice"
        assert obs["predicate"] == "temperature"
        assert obs["object"] == 22.3


class TestInterpretation:
    def test_default_confidence(self):
        interp = interpretation("user:alice", "comfort", "high")
        assert interp["confidence"] == 0.9

    def test_custom_confidence(self):
        interp = interpretation("user:alice", "comfort", "high", confidence=0.75)
        assert interp["confidence"] == 0.75


class TestSituation:
    def test_basic(self):
        sit = situation("user:alice", "meeting")
        assert sit["predicate"] == "isInSituation"
        assert sit["object"] == "meeting"
        assert sit["confidence"] == 0.9

    def test_with_temporal(self):
        sit = situation("user:alice", "meeting", start="2026-01-01T10:00:00Z", end="2026-01-01T11:00:00Z")
        assert sit["start"] == "2026-01-01T10:00:00Z"
        assert sit["end"] == "2026-01-01T11:00:00Z"

    def test_without_temporal(self):
        sit = situation("user:alice", "idle")
        assert "start" not in sit
        assert "end" not in sit


class TestUsermlPayload:
    def test_empty(self):
        p = userml_payload()
        assert p["@model"] == "UserML"
        assert p["layers"]["observation"] == []
        assert p["layers"]["interpretation"] == []
        assert p["layers"]["situation"] == []
        assert p["layers"]["application"] == []

    def test_with_data(self):
        obs = [observation("user:bob", "location", "office")]
        p = userml_payload(observations=obs)
        assert len(p["layers"]["observation"]) == 1
        assert p["layers"]["observation"][0]["subject"] == "user:bob"


class TestSampleSmartOffice:
    def test_structure(self):
        payload = sample_smart_office("user:alice", "2026-01-01T10:00:00Z")
        assert payload["@model"] == "UserML"
        layers = payload["layers"]
        assert len(layers["observation"]) == 2
        assert len(layers["interpretation"]) == 1
        assert len(layers["situation"]) == 1
