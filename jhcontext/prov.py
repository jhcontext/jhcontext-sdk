"""W3C PROV graph builder for PAC-AI using rdflib."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD, PROV

from .crypto import compute_sha256

JH = Namespace("https://jhcontext.com/vocab#")


class PROVGraph:
    """Builder for W3C PROV provenance graphs.

    Supports Entity, Activity, Agent (including Crew delegation) and standard
    PROV relations: wasGeneratedBy, used, wasAssociatedWith, wasDerivedFrom,
    wasInformedBy, actedOnBehalfOf.
    """

    def __init__(self, context_id: str | None = None) -> None:
        self._graph = Graph()
        self._graph.bind("prov", PROV)
        self._graph.bind("jh", JH)
        self.context_id = context_id

    # --- Entity ---

    def add_entity(
        self,
        entity_id: str,
        label: str,
        artifact_type: str | None = None,
        content_hash: str | None = None,
        generated_at: str | None = None,
    ) -> PROVGraph:
        uri = self._uri(entity_id)
        self._graph.add((uri, RDF.type, PROV.Entity))
        self._graph.add((uri, RDFS.label, Literal(label)))
        if artifact_type:
            self._graph.add((uri, JH.artifactType, Literal(artifact_type)))
        if content_hash:
            self._graph.add((uri, JH.contentHash, Literal(content_hash)))
        if generated_at:
            self._graph.add(
                (uri, PROV.generatedAtTime, Literal(generated_at, datatype=XSD.dateTime))
            )
        return self

    # --- Activity ---

    def add_activity(
        self,
        activity_id: str,
        label: str,
        started_at: str | None = None,
        ended_at: str | None = None,
        method: str | None = None,
    ) -> PROVGraph:
        uri = self._uri(activity_id)
        self._graph.add((uri, RDF.type, PROV.Activity))
        self._graph.add((uri, RDFS.label, Literal(label)))
        if started_at:
            self._graph.add(
                (uri, PROV.startedAtTime, Literal(started_at, datatype=XSD.dateTime))
            )
        if ended_at:
            self._graph.add(
                (uri, PROV.endedAtTime, Literal(ended_at, datatype=XSD.dateTime))
            )
        if method:
            self._graph.add((uri, JH.method, Literal(method)))
        return self

    # --- Agent ---

    def add_agent(
        self,
        agent_id: str,
        label: str,
        role: str | None = None,
    ) -> PROVGraph:
        uri = self._uri(agent_id)
        self._graph.add((uri, RDF.type, PROV.Agent))
        self._graph.add((uri, RDFS.label, Literal(label)))
        if role:
            self._graph.add((uri, JH.role, Literal(role)))
        return self

    # --- Crew (Agent group with delegation) ---

    def add_crew(self, crew_id: str, label: str) -> PROVGraph:
        """Register a crew as a prov:Agent + prov:SoftwareAgent.

        A crew groups multiple agents that collaborate on a pipeline.
        Individual agents are linked to the crew via ``acted_on_behalf_of``.
        """
        uri = self._uri(crew_id)
        self._graph.add((uri, RDF.type, PROV.Agent))
        self._graph.add((uri, RDF.type, PROV.SoftwareAgent))
        self._graph.add((uri, RDFS.label, Literal(label)))
        self._graph.add((uri, JH.agentType, Literal("crew")))
        return self

    # --- Relations ---

    def was_generated_by(self, entity_id: str, activity_id: str) -> PROVGraph:
        self._graph.add(
            (self._uri(entity_id), PROV.wasGeneratedBy, self._uri(activity_id))
        )
        return self

    def used(self, activity_id: str, entity_id: str) -> PROVGraph:
        self._graph.add(
            (self._uri(activity_id), PROV.used, self._uri(entity_id))
        )
        return self

    def was_associated_with(self, activity_id: str, agent_id: str) -> PROVGraph:
        self._graph.add(
            (self._uri(activity_id), PROV.wasAssociatedWith, self._uri(agent_id))
        )
        return self

    def was_derived_from(self, derived_id: str, source_id: str) -> PROVGraph:
        self._graph.add(
            (self._uri(derived_id), PROV.wasDerivedFrom, self._uri(source_id))
        )
        return self

    def was_informed_by(self, informed_id: str, informant_id: str) -> PROVGraph:
        self._graph.add(
            (self._uri(informed_id), PROV.wasInformedBy, self._uri(informant_id))
        )
        return self

    def acted_on_behalf_of(self, delegate_id: str, responsible_id: str) -> PROVGraph:
        """Record that *delegate* acted on behalf of *responsible* (W3C PROV).

        Used to express crew membership: an agent that ``actedOnBehalfOf``
        a crew-typed agent is considered a member of that crew.
        """
        self._graph.add(
            (self._uri(delegate_id), PROV.actedOnBehalfOf, self._uri(responsible_id))
        )
        return self

    # --- Serialization ---

    def serialize(self, fmt: str = "turtle") -> str:
        return self._graph.serialize(format=fmt)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-LD dict."""
        import json
        jsonld_str = self._graph.serialize(format="json-ld")
        return json.loads(jsonld_str)

    def digest(self) -> str:
        """SHA-256 of canonical Turtle serialization."""
        turtle = self.serialize("turtle")
        return compute_sha256(turtle.encode("utf-8"))

    # --- Query Helpers ---

    def get_used_entities(self, activity_id: str) -> list[str]:
        """Get all entities used by an activity."""
        uri = self._uri(activity_id)
        return [
            str(o).split("#")[-1] if "#" in str(o) else str(o)
            for o in self._graph.objects(uri, PROV.used)
        ]

    def get_causal_chain(self, entity_id: str) -> list[str]:
        """Recursively trace wasDerivedFrom back to source entities."""
        visited: list[str] = []
        self._trace_derivation(entity_id, visited)
        return visited

    def get_temporal_sequence(self) -> list[dict[str, str]]:
        """Get all activities sorted by startedAtTime."""
        activities = []
        for s in self._graph.subjects(RDF.type, PROV.Activity):
            started = self._graph.value(s, PROV.startedAtTime)
            ended = self._graph.value(s, PROV.endedAtTime)
            label = self._graph.value(s, RDFS.label)
            activities.append({
                "activity_id": str(s).split("#")[-1] if "#" in str(s) else str(s),
                "label": str(label) if label else "",
                "started_at": str(started) if started else "",
                "ended_at": str(ended) if ended else "",
            })
        activities.sort(key=lambda a: a.get("started_at", ""))
        return activities

    def get_all_entities(self) -> list[str]:
        """Get all entity IDs in the graph."""
        return [
            str(s).split("#")[-1] if "#" in str(s) else str(s)
            for s in self._graph.subjects(RDF.type, PROV.Entity)
        ]

    def get_entities_in_chain(self, entity_id: str) -> set[str]:
        """Get all entity IDs in the dependency chain of an entity (recursive)."""
        result: set[str] = set()
        self._collect_dependencies(entity_id, result)
        return result

    def query(self, sparql: str) -> list[dict[str, str]]:
        """Execute a SPARQL query and return results as list of dicts."""
        results = self._graph.query(sparql)
        return [
            {str(var): str(val) for var, val in zip(results.vars, row)}
            for row in results
        ]

    # --- Crew Query Helpers ---

    def get_crew_agents(self, crew_id: str) -> list[str]:
        """Get all agents that acted on behalf of the given crew."""
        crew_uri = self._uri(crew_id)
        return [
            str(s).split("#")[-1] if "#" in str(s) else str(s)
            for s in self._graph.subjects(PROV.actedOnBehalfOf, crew_uri)
        ]

    def get_crew_activities(self, crew_id: str) -> list[str]:
        """Get all activities performed by agents in the given crew."""
        crew_uri = self._uri(crew_id)
        activities = []
        for agent in self._graph.subjects(PROV.actedOnBehalfOf, crew_uri):
            for activity in self._graph.subjects(PROV.wasAssociatedWith, agent):
                aid = str(activity).split("#")[-1] if "#" in str(activity) else str(activity)
                if aid not in activities:
                    activities.append(aid)
        return activities

    def get_agent_crew(self, agent_id: str) -> str | None:
        """Get the crew an agent belongs to (via actedOnBehalfOf), or None."""
        agent_uri = self._uri(agent_id)
        crew = self._graph.value(agent_uri, PROV.actedOnBehalfOf)
        if crew is None:
            return None
        return str(crew).split("#")[-1] if "#" in str(crew) else str(crew)

    @property
    def graph(self) -> Graph:
        return self._graph

    # --- Internal ---

    def _uri(self, local_id: str) -> URIRef:
        if local_id.startswith("http") or local_id.startswith("did:"):
            return URIRef(local_id)
        return JH[local_id]

    def _trace_derivation(self, entity_id: str, visited: list[str]) -> None:
        uri = self._uri(entity_id)
        for source in self._graph.objects(uri, PROV.wasDerivedFrom):
            source_id = str(source).split("#")[-1] if "#" in str(source) else str(source)
            if source_id not in visited:
                visited.append(source_id)
                self._trace_derivation(source_id, visited)

    def _collect_dependencies(self, entity_id: str, result: set[str]) -> None:
        uri = self._uri(entity_id)
        for source in self._graph.objects(uri, PROV.wasDerivedFrom):
            source_id = str(source).split("#")[-1] if "#" in str(source) else str(source)
            if source_id not in result:
                result.add(source_id)
                self._collect_dependencies(source_id, result)
        for activity in self._graph.subjects(PROV.wasGeneratedBy):
            if (uri, PROV.wasGeneratedBy, activity) in self._graph:
                for used_entity in self._graph.objects(activity, PROV.used):
                    used_id = str(used_entity).split("#")[-1] if "#" in str(used_entity) else str(used_entity)
                    if used_id not in result:
                        result.add(used_id)
                        self._collect_dependencies(used_id, result)
