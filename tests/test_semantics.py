"""Tests for jhcontext.semantics — protocol v0.5 (Heckmann-correct mainpart)."""

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
        assert obs["administration"]["group"] == "Observation"
        assert obs["mainpart"]["subject"] == "user:alice"
        assert obs["mainpart"]["auxiliary"] == "hasProperty"
        assert obs["mainpart"]["predicate"] == "temperature"
        assert obs["mainpart"]["object"] == 22.3

    def test_with_range(self):
        obs = observation("user:alice", "temperature", 22.3,
                          range_="float-degrees-celsius")
        assert obs["mainpart"]["range"] == "float-degrees-celsius"

    def test_no_layer_field(self):
        obs = observation("user:alice", "temperature", 22.3)
        assert "layer" not in obs

    def test_with_source(self):
        obs = observation("user:alice", "temperature", 22.3, source="sensor:t1")
        assert obs["explanation"]["source"] == "sensor:t1"

    def test_without_source_has_no_explanation_box(self):
        obs = observation("user:alice", "temperature", 22.3)
        assert "explanation" not in obs


class TestInterpretation:
    def test_default_confidence(self):
        interp = interpretation("user:alice", "comfort", "high")
        assert interp["administration"]["group"] == "Interpretation"
        assert interp["mainpart"]["auxiliary"] == "hasAssessment"
        assert interp["mainpart"]["object"] == "high"
        assert interp["explanation"]["confidence"] == 0.9

    def test_custom_confidence(self):
        interp = interpretation("user:alice", "comfort", "high", confidence=0.75)
        assert interp["explanation"]["confidence"] == 0.75

    def test_with_creator_and_method(self):
        interp = interpretation("u:a", "p", "v", creator="did:x", method="m1")
        assert interp["explanation"]["creator"] == "did:x"
        assert interp["explanation"]["method"] == "m1"

    def test_with_range(self):
        interp = interpretation("u:a", "comfort", "high",
                                range_="low-medium-high")
        assert interp["mainpart"]["range"] == "low-medium-high"


class TestSituation:
    def test_basic(self):
        sit = situation("user:alice", "meeting")
        assert sit["administration"]["group"] == "Situation"
        assert sit["mainpart"]["auxiliary"] == "isInSituation"
        assert sit["mainpart"]["predicate"] == "activity"
        assert sit["mainpart"]["object"] == "meeting"
        assert sit["explanation"]["confidence"] == 0.9

    def test_with_temporal(self):
        sit = situation("user:alice", "meeting",
                        start="2026-01-01T10:00:00Z",
                        end="2026-01-01T11:00:00Z",
                        durability="one hour")
        assert sit["situation"]["start"] == "2026-01-01T10:00:00Z"
        assert sit["situation"]["end"] == "2026-01-01T11:00:00Z"
        assert sit["situation"]["durability"] == "one hour"

    def test_with_location(self):
        sit = situation("user:alice", "meeting",
                        location="ConferenceRoomA")
        assert sit["situation"]["location"] == "ConferenceRoomA"

    def test_without_temporal_or_spatial_has_no_situation_box(self):
        sit = situation("user:alice", "idle")
        assert "situation" not in sit


class TestApplication:
    def test_basic(self):
        app = application("notification:n-1", "shouldBeDelivered", False,
                          range_="boolean")
        assert app["administration"]["group"] == "Application"
        assert app["mainpart"]["auxiliary"] == "hasPolicy"
        assert app["mainpart"]["range"] == "boolean"
        assert app["mainpart"]["object"] is False

    def test_custom_auxiliary(self):
        app = application("task:t-1", "requires", "approval",
                          auxiliary="hasRequirement")
        assert app["mainpart"]["auxiliary"] == "hasRequirement"


class TestSampleSmartOffice:
    def test_structure(self):
        payload = sample_smart_office("user:alice", "2026-01-01T10:00:00Z")
        assert isinstance(payload, list)
        assert len(payload) == 4
        groups = [s["administration"]["group"] for s in payload]
        assert groups.count("Observation") == 2
        assert groups.count("Interpretation") == 1
        assert groups.count("Situation") == 1

    def test_each_is_atomic_heckmann_shape(self):
        payload = sample_smart_office("user:alice", "2026-01-01T10:00:00Z")
        for stmt in payload:
            assert stmt["@model"] == "UserML"
            assert "layer" not in stmt
            assert "mainpart" in stmt
            assert "administration" in stmt
            assert "group" in stmt["administration"]
            required_mainpart_slots = {"subject", "auxiliary", "predicate", "object"}
            assert set(stmt["mainpart"].keys()) >= required_mainpart_slots
