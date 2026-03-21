"""Tests for jhcontext.models — Pydantic data models."""

import pytest
from jhcontext.models import (
    Artifact,
    ArtifactType,
    ComplianceBlock,
    DataCategory,
    Decision,
    DecisionInfluence,
    Envelope,
    EnvelopeStatus,
    PrivacyBlock,
    Proof,
    ProvenanceRef,
    RiskLevel,
    AbstractionLevel,
    TemporalScope,
)


class TestEnums:
    def test_artifact_type_values(self):
        assert ArtifactType.TOKEN_SEQUENCE == "token_sequence"
        assert ArtifactType.EMBEDDING == "embedding"
        assert ArtifactType.SEMANTIC_EXTRACTION == "semantic_extraction"
        assert ArtifactType.TOOL_RESULT == "tool_result"

    def test_risk_level_values(self):
        assert RiskLevel.LOW == "low"
        assert RiskLevel.MEDIUM == "medium"
        assert RiskLevel.HIGH == "high"

    def test_abstraction_level_values(self):
        assert AbstractionLevel.OBSERVATION == "observation"
        assert AbstractionLevel.INTERPRETATION == "interpretation"
        assert AbstractionLevel.SITUATION == "situation"

    def test_envelope_status_values(self):
        assert EnvelopeStatus.ACTIVE == "active"
        assert EnvelopeStatus.EXPIRED == "expired"
        assert EnvelopeStatus.DELETED == "deleted"

    def test_data_category_values(self):
        assert DataCategory.BEHAVIORAL == "behavioral"
        assert DataCategory.BIOMETRIC == "biometric"
        assert DataCategory.SENSITIVE == "sensitive"


class TestArtifact:
    def test_defaults(self):
        art = Artifact(type=ArtifactType.EMBEDDING)
        assert art.artifact_id.startswith("art-")
        assert art.type == ArtifactType.EMBEDDING
        assert art.storage_ref is None
        assert art.content_hash is None
        assert art.model is None
        assert art.deterministic is False
        assert art.confidence is None
        assert art.dimensions is None
        assert art.metadata == {}

    def test_full_construction(self):
        art = Artifact(
            artifact_id="art-test",
            type=ArtifactType.TOKEN_SEQUENCE,
            storage_ref="s3://bucket/key",
            content_hash="sha256:abc",
            model="gpt-4",
            deterministic=True,
            confidence=0.95,
            dimensions=1536,
            metadata={"source": "test"},
        )
        assert art.artifact_id == "art-test"
        assert art.model == "gpt-4"
        assert art.dimensions == 1536
        assert art.metadata["source"] == "test"


class TestDecisionInfluence:
    def test_defaults(self):
        di = DecisionInfluence(agent="agent-1", categories=["health"])
        assert di.abstraction_level == AbstractionLevel.SITUATION
        assert di.temporal_scope == TemporalScope.CURRENT
        assert di.influence_weights == {}
        assert di.confidence == 0.0

    def test_custom_values(self):
        di = DecisionInfluence(
            agent="agent-2",
            categories=["education", "equity"],
            abstraction_level=AbstractionLevel.OBSERVATION,
            temporal_scope=TemporalScope.HISTORICAL,
            influence_weights={"grade": 0.8},
            confidence=0.9,
        )
        assert di.influence_weights["grade"] == 0.8


class TestPrivacyBlock:
    def test_defaults(self):
        pb = PrivacyBlock()
        assert pb.data_category == DataCategory.BEHAVIORAL
        assert pb.legal_basis == "consent"
        assert pb.retention == "P7D"
        assert pb.storage_policy == "centralized-encrypted"
        assert pb.feature_suppression == []


class TestComplianceBlock:
    def test_defaults(self):
        cb = ComplianceBlock()
        assert cb.risk_level == RiskLevel.MEDIUM
        assert cb.human_oversight_required is False
        assert cb.model_card_ref is None


class TestProof:
    def test_defaults(self):
        p = Proof()
        assert p.canonicalization == "URDNA2015"
        assert p.content_hash is None
        assert p.signature is None
        assert p.signer is None


class TestEnvelope:
    def test_defaults(self):
        env = Envelope()
        assert env.context_id.startswith("ctx-")
        assert env.schema_version == "jh:0.3"
        assert env.producer == ""
        assert env.status == EnvelopeStatus.ACTIVE
        assert env.semantic_payload == []
        assert env.artifacts_registry == []
        assert env.passed_artifact_pointer is None
        assert env.decision_influence == []
        assert isinstance(env.privacy, PrivacyBlock)
        assert isinstance(env.compliance, ComplianceBlock)
        assert isinstance(env.provenance_ref, ProvenanceRef)
        assert isinstance(env.proof, Proof)

    def test_to_jsonld(self):
        env = Envelope(context_id="ctx-test", producer="did:example:1")
        jld = env.to_jsonld()
        assert jld["@context"]["jh"] == "https://jhcontext.com/vocab#"
        assert jld["@type"] == "jh:Envelope"
        assert jld["context_id"] == "ctx-test"
        assert jld["producer"] == "did:example:1"
        assert "proof" in jld

    def test_to_jsonld_exclude_proof(self):
        env = Envelope(context_id="ctx-test")
        jld = env.to_jsonld(include_proof=False)
        assert "proof" not in jld
        assert "@context" in jld

    def test_model_validate_roundtrip(self):
        env = Envelope(
            context_id="ctx-round",
            producer="did:example:agent",
            scope="healthcare",
        )
        data = env.model_dump(mode="json")
        env2 = Envelope.model_validate(data)
        assert env2.context_id == "ctx-round"
        assert env2.scope == "healthcare"


class TestDecision:
    def test_defaults(self):
        dec = Decision(context_id="ctx-1")
        assert dec.decision_id.startswith("dec-")
        assert dec.context_id == "ctx-1"
        assert dec.passed_artifact_id is None
        assert dec.outcome == {}
        assert dec.agent_id == ""

    def test_full_construction(self):
        dec = Decision(
            decision_id="dec-test",
            context_id="ctx-1",
            passed_artifact_id="art-1",
            outcome={"action": "approve"},
            agent_id="agent-1",
        )
        assert dec.outcome["action"] == "approve"
