"""Tests for jhcontext.prov — PROVGraph W3C PROV builder."""

import pytest
from jhcontext.prov import PROVGraph


class TestPROVGraphConstruction:
    def test_empty_graph(self):
        pg = PROVGraph("ctx-test")
        assert pg.context_id == "ctx-test"
        assert pg.graph is not None

    def test_add_entity(self):
        pg = PROVGraph()
        pg.add_entity("ent-1", "Test Entity", artifact_type="embedding", content_hash="sha256:abc")
        entities = pg.get_all_entities()
        assert len(entities) == 1
        assert "ent-1" in entities[0]

    def test_add_activity(self):
        pg = PROVGraph()
        pg.add_activity(
            "act-1", "Analysis",
            started_at="2026-01-01T10:00:00Z",
            ended_at="2026-01-01T10:30:00Z",
            method="LLM inference",
        )
        seq = pg.get_temporal_sequence()
        assert len(seq) == 1
        assert seq[0]["label"] == "Analysis"
        assert "2026-01-01T10:00:00" in seq[0]["started_at"]

    def test_add_agent(self):
        pg = PROVGraph()
        pg.add_agent("agent-1", "Sensor Agent", role="data_collector")
        turtle = pg.serialize("turtle")
        assert "Sensor Agent" in turtle


class TestPROVGraphRelations:
    def test_was_generated_by(self):
        pg = PROVGraph()
        pg.add_entity("ent-1", "Output")
        pg.add_activity("act-1", "Process")
        pg.was_generated_by("ent-1", "act-1")
        turtle = pg.serialize()
        assert "wasGeneratedBy" in turtle

    def test_used(self):
        pg = PROVGraph()
        pg.add_activity("act-1", "Process")
        pg.add_entity("ent-1", "Input")
        pg.used("act-1", "ent-1")
        used = pg.get_used_entities("act-1")
        assert len(used) == 1
        assert "ent-1" in used[0]

    def test_was_associated_with(self):
        pg = PROVGraph()
        pg.add_activity("act-1", "Process")
        pg.add_agent("agent-1", "Agent")
        pg.was_associated_with("act-1", "agent-1")
        turtle = pg.serialize()
        assert "wasAssociatedWith" in turtle

    def test_was_derived_from(self):
        pg = PROVGraph()
        pg.add_entity("ent-derived", "Derived")
        pg.add_entity("ent-source", "Source")
        pg.was_derived_from("ent-derived", "ent-source")
        chain = pg.get_causal_chain("ent-derived")
        assert len(chain) == 1
        assert "ent-source" in chain[0]

    def test_was_informed_by(self):
        pg = PROVGraph()
        pg.add_activity("act-2", "Later")
        pg.add_activity("act-1", "Earlier")
        pg.was_informed_by("act-2", "act-1")
        turtle = pg.serialize()
        assert "wasInformedBy" in turtle

    def test_fluent_chaining(self):
        pg = (
            PROVGraph("ctx-chain")
            .add_entity("e1", "Entity 1")
            .add_entity("e2", "Entity 2")
            .add_activity("a1", "Activity")
            .add_agent("ag1", "Agent")
            .was_generated_by("e2", "a1")
            .used("a1", "e1")
            .was_associated_with("a1", "ag1")
            .was_derived_from("e2", "e1")
        )
        assert len(pg.get_all_entities()) == 2


class TestPROVGraphQueries:
    @pytest.fixture
    def healthcare_prov(self):
        """Healthcare scenario PROV graph."""
        pg = PROVGraph("ctx-health")
        # Entities
        pg.add_entity("vitals", "Patient Vitals", artifact_type="token_sequence")
        pg.add_entity("history", "Medical History", artifact_type="token_sequence")
        pg.add_entity("recommendation", "AI Recommendation", artifact_type="semantic_extraction")
        # Activities
        pg.add_activity("ai-analysis", "AI Analysis",
                        started_at="2026-01-01T10:00:00Z",
                        ended_at="2026-01-01T10:01:00Z")
        pg.add_activity("doctor-review", "Doctor Review",
                        started_at="2026-01-01T10:05:00Z",
                        ended_at="2026-01-01T10:15:00Z")
        # Relations
        pg.used("ai-analysis", "vitals")
        pg.used("ai-analysis", "history")
        pg.was_generated_by("recommendation", "ai-analysis")
        pg.was_derived_from("recommendation", "vitals")
        pg.was_derived_from("recommendation", "history")
        return pg

    def test_get_used_entities(self, healthcare_prov):
        used = healthcare_prov.get_used_entities("ai-analysis")
        assert len(used) == 2

    def test_get_causal_chain(self, healthcare_prov):
        chain = healthcare_prov.get_causal_chain("recommendation")
        assert len(chain) == 2  # vitals, history

    def test_get_temporal_sequence(self, healthcare_prov):
        seq = healthcare_prov.get_temporal_sequence()
        assert len(seq) == 2
        # Should be sorted by start time
        assert seq[0]["label"] == "AI Analysis"
        assert seq[1]["label"] == "Doctor Review"

    def test_get_all_entities(self, healthcare_prov):
        entities = healthcare_prov.get_all_entities()
        assert len(entities) == 3

    def test_get_entities_in_chain(self, healthcare_prov):
        chain = healthcare_prov.get_entities_in_chain("recommendation")
        # Should include vitals and history (via wasDerivedFrom and used)
        assert len(chain) >= 2


class TestPROVGraphSerialization:
    def test_serialize_turtle(self):
        pg = PROVGraph().add_entity("e1", "Entity")
        turtle = pg.serialize("turtle")
        assert isinstance(turtle, str)
        assert "Entity" in turtle

    def test_serialize_jsonld(self):
        pg = PROVGraph().add_entity("e1", "Entity")
        d = pg.to_dict()
        assert isinstance(d, (dict, list))

    def test_digest(self):
        pg = PROVGraph().add_entity("e1", "Entity")
        digest = pg.digest()
        assert isinstance(digest, str)
        assert len(digest) == 64  # SHA-256 hex

    def test_sparql_query(self):
        pg = PROVGraph()
        pg.add_entity("e1", "Test Entity")
        results = pg.query("""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?label WHERE { ?s rdfs:label ?label }
        """)
        assert len(results) >= 1
        labels = [r["label"] for r in results]
        assert "Test Entity" in labels
