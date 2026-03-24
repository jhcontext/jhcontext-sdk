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


class TestPROVGraphCrewDelegation:
    """Tests for crew-level delegation via prov:actedOnBehalfOf."""

    @pytest.fixture
    def crew_prov(self):
        """Healthcare pipeline with a clinical crew."""
        pg = PROVGraph("ctx-crew")
        # Register crew
        pg.add_crew("crew-clinical", "Clinical Pipeline Crew")
        # Register agents and delegate to crew
        pg.add_agent("did:hospital:sensor-agent", "Sensor Agent", role="sensor")
        pg.add_agent("did:hospital:situation-agent", "Situation Agent", role="situation")
        pg.add_agent("did:hospital:decision-agent", "Decision Agent", role="decision")
        pg.acted_on_behalf_of("did:hospital:sensor-agent", "crew-clinical")
        pg.acted_on_behalf_of("did:hospital:situation-agent", "crew-clinical")
        pg.acted_on_behalf_of("did:hospital:decision-agent", "crew-clinical")
        # Oversight agent outside the crew
        pg.add_agent("did:hospital:dr-chen", "Dr. Chen", role="physician_oversight")
        # Activities
        pg.add_activity("act-sensor", "sensor",
                        started_at="2026-01-01T10:00:00Z",
                        ended_at="2026-01-01T10:01:00Z")
        pg.add_activity("act-situation", "situation",
                        started_at="2026-01-01T10:01:00Z",
                        ended_at="2026-01-01T10:02:00Z")
        pg.add_activity("act-decision", "decision",
                        started_at="2026-01-01T10:02:00Z",
                        ended_at="2026-01-01T10:03:00Z")
        pg.add_activity("act-oversight", "physician_oversight",
                        started_at="2026-01-01T10:05:00Z",
                        ended_at="2026-01-01T10:15:00Z")
        # Link activities to agents
        pg.was_associated_with("act-sensor", "did:hospital:sensor-agent")
        pg.was_associated_with("act-situation", "did:hospital:situation-agent")
        pg.was_associated_with("act-decision", "did:hospital:decision-agent")
        pg.was_associated_with("act-oversight", "did:hospital:dr-chen")
        return pg

    def test_add_crew(self):
        pg = PROVGraph()
        pg.add_crew("crew-test", "Test Crew")
        turtle = pg.serialize()
        assert "SoftwareAgent" in turtle
        assert "Test Crew" in turtle
        assert "crew" in turtle  # jh:agentType "crew"

    def test_acted_on_behalf_of(self):
        pg = PROVGraph()
        pg.add_agent("agent-1", "Agent")
        pg.add_crew("crew-1", "Crew")
        pg.acted_on_behalf_of("agent-1", "crew-1")
        turtle = pg.serialize()
        assert "actedOnBehalfOf" in turtle

    def test_get_crew_agents(self, crew_prov):
        agents = crew_prov.get_crew_agents("crew-clinical")
        assert len(agents) == 3
        agent_strs = " ".join(agents)
        assert "sensor-agent" in agent_strs
        assert "situation-agent" in agent_strs
        assert "decision-agent" in agent_strs

    def test_get_crew_activities(self, crew_prov):
        activities = crew_prov.get_crew_activities("crew-clinical")
        assert len(activities) == 3
        activity_strs = " ".join(activities)
        assert "act-sensor" in activity_strs
        assert "act-situation" in activity_strs
        assert "act-decision" in activity_strs
        # Oversight should NOT be in the crew activities
        assert "act-oversight" not in activity_strs

    def test_get_agent_crew(self, crew_prov):
        crew = crew_prov.get_agent_crew("did:hospital:sensor-agent")
        assert crew is not None
        assert "crew-clinical" in crew

    def test_get_agent_crew_none(self, crew_prov):
        crew = crew_prov.get_agent_crew("did:hospital:dr-chen")
        assert crew is None

    def test_crew_sparql_query(self, crew_prov):
        """Query all activities from a crew using raw SPARQL."""
        results = crew_prov.query("""
            PREFIX prov: <http://www.w3.org/ns/prov#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX jh: <https://jhcontext.com/vocab#>
            SELECT ?activity ?label WHERE {
                ?agent prov:actedOnBehalfOf jh:crew-clinical .
                ?activity prov:wasAssociatedWith ?agent .
                ?activity rdfs:label ?label .
            }
            ORDER BY ?activity
        """)
        assert len(results) == 3
        labels = sorted(r["label"] for r in results)
        assert labels == ["decision", "sensor", "situation"]

    def test_fluent_chaining_with_crew(self):
        pg = (
            PROVGraph("ctx-fluent")
            .add_crew("crew-rec", "Recommendation Crew")
            .add_agent("agent-profile", "Profile Agent", role="profile")
            .acted_on_behalf_of("agent-profile", "crew-rec")
        )
        agents = pg.get_crew_agents("crew-rec")
        assert len(agents) == 1
