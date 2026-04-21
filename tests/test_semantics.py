"""Tests for jhcontext.semantics — UserML helpers (protocol v0.4, Heckmann-faithful)."""

from jhcontext.semantics import (
    observation,
    interpretation,
    situation,
    application,
    sample_smart_office,
)


class TestObservation:
    def test_basic(self):
        obs = observation("user:alice", "temperature", 22.3)
        assert obs["@model"] == "UserML"
        assert obs["layer"] == "observation"
        assert obs["mainpart"]["subject"] == "user:alice"
        assert obs["mainpart"]["auxiliary"] == "hasProperty"
        assert obs["mainpart"]["predicate"] == "temperature"
        assert obs["mainpart"]["range"] == 22.3

    def test_with_source(self):
        obs = observation("user:alice", "temperature", 22.3, source="sensor:t1")
        assert obs["explanation"]["source"] == "sensor:t1"

    def test_without_source_has_no_explanation_box(self):
        obs = observation("user:alice", "temperature", 22.3)
        assert "explanation" not in obs


class TestInterpretation:
    def test_default_confidence(self):
        interp = interpretation("user:alice", "comfort", "high")
        assert interp["layer"] == "interpretation"
        assert interp["mainpart"]["auxiliary"] == "hasAssessment"
        assert interp["explanation"]["confidence"] == 0.9

    def test_custom_confidence(self):
        interp = interpretation("user:alice", "comfort", "high", confidence=0.75)
        assert interp["explanation"]["confidence"] == 0.75

    def test_with_creator_and_method(self):
        interp = interpretation("u:a", "p", "v", creator="did:x", method="m1")
        assert interp["explanation"]["creator"] == "did:x"
        assert interp["explanation"]["method"] == "m1"


class TestSituation:
    def test_basic(self):
        sit = situation("user:alice", "meeting")
        assert sit["layer"] == "situation"
        assert sit["mainpart"]["auxiliary"] == "isInSituation"
        assert sit["mainpart"]["predicate"] == "activity"
        assert sit["mainpart"]["range"] == "meeting"
        assert sit["explanation"]["confidence"] == 0.9

    def test_with_temporal(self):
        sit = situation("user:alice", "meeting",
                        start="2026-01-01T10:00:00Z",
                        end="2026-01-01T11:00:00Z")
        assert sit["situation"]["start"] == "2026-01-01T10:00:00Z"
        assert sit["situation"]["end"] == "2026-01-01T11:00:00Z"

    def test_without_temporal_has_no_situation_box(self):
        sit = situation("user:alice", "idle")
        assert "situation" not in sit


class TestApplication:
    def test_basic(self):
        app = application("notification:n-1", "shouldBeDelivered", False)
        assert app["layer"] == "application"
        assert app["mainpart"]["auxiliary"] == "hasPolicy"
        assert app["mainpart"]["range"] is False

    def test_custom_auxiliary(self):
        app = application("task:t-1", "requires", "approval", auxiliary="hasRequirement")
        assert app["mainpart"]["auxiliary"] == "hasRequirement"


class TestSampleSmartOffice:
    def test_structure(self):
        payload = sample_smart_office("user:alice", "2026-01-01T10:00:00Z")
        assert isinstance(payload, list)
        assert len(payload) == 4
        layers = [s["layer"] for s in payload]
        assert layers.count("observation") == 2
        assert layers.count("interpretation") == 1
        assert layers.count("situation") == 1

    def test_each_is_atomic(self):
        payload = sample_smart_office("user:alice", "2026-01-01T10:00:00Z")
        for stmt in payload:
            assert stmt["@model"] == "UserML"
            assert "layer" in stmt
            assert "mainpart" in stmt
            assert set(stmt["mainpart"].keys()) >= {"subject", "auxiliary", "predicate", "range"}
