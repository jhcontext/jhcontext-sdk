"""Benchmarks for PAC-AI SDK — baseline overhead measurements.

Measures PAC-AI operations against equivalent baseline operations
(plain JSON serialization, dict lookups) to quantify protocol overhead.

Run with:
    pytest tests/test_benchmarks.py -v --benchmark-warmup=on --benchmark-min-rounds=1000
"""

import json

import pytest

from jhcontext.builder import EnvelopeBuilder
from jhcontext.canonicalize import canonicalize
from jhcontext.crypto import compute_sha256, sign_envelope
from jhcontext.models import ArtifactType, RiskLevel
from jhcontext.prov import PROVGraph


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_payload():
    """Realistic UserML v0.4 semantic payload (flat list of atomic statements)."""
    def stmt(layer, subject, aux, pred, rng, **extras):
        s = {"@model": "UserML", "layer": layer,
             "mainpart": {"subject": subject, "auxiliary": aux,
                          "predicate": pred, "range": rng}}
        s.update(extras)
        return s

    return [
        stmt("observation", "patient:P-001", "hasVital", "heart_rate", "82bpm"),
        stmt("observation", "patient:P-001", "hasLab", "troponin", "0.04ng/mL"),
        stmt("observation", "patient:P-001", "hasImaging", "ct_finding",
             "normal_sinus_rhythm"),
        stmt("interpretation", "patient:P-001", "hasAssessment",
             "cardiac_risk", "low",
             explanation={"confidence": 0.87}),
        stmt("interpretation", "patient:P-001", "hasAssessment",
             "clinical_pattern", "stable_vitals",
             explanation={"confidence": 0.9}),
        stmt("situation", "patient:P-001", "isInSituation", "activity",
             "monitoring_required",
             explanation={"confidence": 0.9}),
        stmt("application", "patient:P-001", "hasPolicy",
             "treatment_recommendation", "continue_monitoring"),
    ]


@pytest.fixture
def built_envelope(sample_payload):
    """Pre-built envelope (unsigned) for component-level benchmarks."""
    return (
        EnvelopeBuilder()
        .set_producer("did:example:bench-agent")
        .set_scope("healthcare")
        .set_ttl("PT1H")
        .set_risk_level(RiskLevel.HIGH)
        .set_human_oversight(True)
        .set_semantic_payload(sample_payload)
        .add_artifact(
            artifact_id="art-bench-1",
            artifact_type=ArtifactType.SEMANTIC_EXTRACTION,
            content_hash="sha256:benchmarkdata",
            model="gpt-4o",
        )
        .build()
    )


@pytest.fixture
def prov_graph_500():
    """PROVGraph with 500 entities in a linear derivation chain."""
    pg = PROVGraph("ctx-bench-500")
    for i in range(500):
        pg.add_entity(f"ent-{i}", f"Entity {i}")
        pg.add_activity(
            f"act-{i}",
            f"Activity {i}",
            started_at=f"2026-01-01T{i // 3600:02d}:{(i % 3600) // 60:02d}:{i % 60:02d}Z",
            ended_at=f"2026-01-01T{i // 3600:02d}:{(i % 3600) // 60:02d}:{i % 60:02d}Z",
        )
        pg.add_agent(f"agent-{i % 5}", f"Agent {i % 5}")
        pg.was_associated_with(f"act-{i}", f"agent-{i % 5}")
        pg.was_generated_by(f"ent-{i}", f"act-{i}")
        if i > 0:
            pg.used(f"act-{i}", f"ent-{i - 1}")
            pg.was_derived_from(f"ent-{i}", f"ent-{i - 1}")
    return pg


@pytest.fixture
def baseline_dict_500():
    """Plain Python dict with 500 entries + adjacency list for traversal baseline."""
    entities = {f"ent-{i}": {"label": f"Entity {i}", "data": f"value-{i}"} for i in range(500)}
    adjacency = {f"ent-{i}": f"ent-{i - 1}" for i in range(1, 500)}
    return entities, adjacency


# ---------------------------------------------------------------------------
# 1. Envelope Construction Benchmarks
# ---------------------------------------------------------------------------

class TestEnvelopeBenchmarks:

    def test_baseline_json_serialization(self, benchmark, sample_payload):
        """BASELINE: Pydantic model_dump + json.dumps — no PROV, no signing."""
        env = (
            EnvelopeBuilder()
            .set_producer("did:example:bench-agent")
            .set_scope("healthcare")
            .set_ttl("PT1H")
            .set_risk_level(RiskLevel.HIGH)
            .set_semantic_payload(sample_payload)
            .add_artifact(
                artifact_id="art-bench-1",
                artifact_type=ArtifactType.SEMANTIC_EXTRACTION,
                content_hash="sha256:benchmarkdata",
                model="gpt-4o",
            )
            .build()
        )

        def baseline():
            d = env.model_dump(mode="json", exclude_none=True)
            return json.dumps(d, separators=(",", ":"))

        benchmark(baseline)

    def test_envelope_construction_with_signing(self, benchmark, sample_payload):
        """PAC-AI: Full envelope build with Ed25519 signing."""
        def build_signed():
            return (
                EnvelopeBuilder()
                .set_producer("did:example:bench-agent")
                .set_scope("healthcare")
                .set_ttl("PT1H")
                .set_risk_level(RiskLevel.HIGH)
                .set_human_oversight(True)
                .set_semantic_payload(sample_payload)
                .add_artifact(
                    artifact_id="art-bench-1",
                    artifact_type=ArtifactType.SEMANTIC_EXTRACTION,
                    content_hash="sha256:benchmarkdata",
                    model="gpt-4o",
                )
                .sign("did:example:signer")
                .build()
            )

        benchmark(build_signed)

    def test_envelope_construction_without_signing(self, benchmark, sample_payload):
        """PAC-AI: Envelope build without signing (hash only)."""
        def build_unsigned():
            return (
                EnvelopeBuilder()
                .set_producer("did:example:bench-agent")
                .set_scope("healthcare")
                .set_ttl("PT1H")
                .set_risk_level(RiskLevel.HIGH)
                .set_semantic_payload(sample_payload)
                .add_artifact(
                    artifact_id="art-bench-1",
                    artifact_type=ArtifactType.SEMANTIC_EXTRACTION,
                    content_hash="sha256:benchmarkdata",
                    model="gpt-4o",
                )
                .build()
            )

        benchmark(build_unsigned)


# ---------------------------------------------------------------------------
# 2. Component-Level Benchmarks
# ---------------------------------------------------------------------------

class TestComponentBenchmarks:

    def test_canonicalization_only(self, benchmark, built_envelope):
        """Isolate: JSON-LD canonicalization cost."""
        jsonld = built_envelope.to_jsonld(include_proof=False)
        benchmark(canonicalize, jsonld)

    def test_sha256_hashing_only(self, benchmark, built_envelope):
        """Isolate: SHA-256 hashing cost."""
        canonical = canonicalize(built_envelope.to_jsonld(include_proof=False))
        data = canonical.encode("utf-8")
        benchmark(compute_sha256, data)

    def test_ed25519_signing_only(self, benchmark, built_envelope):
        """Isolate: Ed25519 signing cost (includes canonicalization + hashing)."""
        benchmark(sign_envelope, built_envelope, "did:example:signer")

    def test_model_dump_only(self, benchmark, built_envelope):
        """Isolate: Pydantic model_dump cost."""
        benchmark(built_envelope.model_dump, mode="json", exclude_none=True)

    def test_to_jsonld_only(self, benchmark, built_envelope):
        """Isolate: to_jsonld (model_dump + @context/@type injection)."""
        benchmark(built_envelope.to_jsonld, include_proof=False)


# ---------------------------------------------------------------------------
# 3. PROV Point Query Benchmarks (500 entities)
# ---------------------------------------------------------------------------

class TestProvPointQueryBenchmarks:

    def test_prov_point_query_500(self, benchmark, prov_graph_500):
        """PAC-AI: Single-entity point query on 500-entity PROV graph."""
        benchmark(prov_graph_500.get_used_entities, "act-250")

    def test_baseline_dict_lookup_500(self, benchmark, baseline_dict_500):
        """BASELINE: Plain dict lookup with 500 entries."""
        entities, _ = baseline_dict_500
        benchmark(entities.get, "ent-250")

    def test_prov_get_all_entities_500(self, benchmark, prov_graph_500):
        """PAC-AI: Get all entities in 500-entity graph."""
        benchmark(prov_graph_500.get_all_entities)

    def test_prov_temporal_sequence_500(self, benchmark, prov_graph_500):
        """PAC-AI: Get temporal sequence (sorted activities) in 500-entity graph."""
        benchmark(prov_graph_500.get_temporal_sequence)


# ---------------------------------------------------------------------------
# 4. PROV Full Traversal Benchmarks (500 entities)
# ---------------------------------------------------------------------------

class TestProvTraversalBenchmarks:

    @pytest.mark.benchmark(min_rounds=10)
    def test_prov_full_traversal_500(self, benchmark, prov_graph_500):
        """PAC-AI: Full causal chain traversal from last entity (500 hops)."""
        benchmark(prov_graph_500.get_causal_chain, "ent-499")

    def test_baseline_dict_traversal_500(self, benchmark, baseline_dict_500):
        """BASELINE: Recursive dict traversal over 500-node adjacency list."""
        _, adjacency = baseline_dict_500

        def traverse(start):
            visited = []
            current = start
            while current in adjacency:
                current = adjacency[current]
                visited.append(current)
            return visited

        benchmark(traverse, "ent-499")

    @pytest.mark.benchmark(min_rounds=10)
    def test_prov_get_entities_in_chain_500(self, benchmark, prov_graph_500):
        """PAC-AI: Collect all dependencies recursively (500 entities)."""
        benchmark(prov_graph_500.get_entities_in_chain, "ent-499")
