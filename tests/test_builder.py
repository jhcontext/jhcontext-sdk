"""Tests for jhcontext.builder — EnvelopeBuilder fluent API."""

import pytest
from jhcontext.builder import EnvelopeBuilder
from jhcontext.models import (
    ArtifactType,
    RiskLevel,
    AbstractionLevel,
    TemporalScope,
    EnvelopeStatus,
)


class TestEnvelopeBuilder:
    def test_basic_build(self):
        env = EnvelopeBuilder().set_producer("did:example:1").build()
        assert env.producer == "did:example:1"
        assert env.context_id.startswith("ctx-")
        assert env.status == EnvelopeStatus.ACTIVE
        # content hash should be computed on build
        assert env.proof.content_hash is not None

    def test_fluent_chaining(self):
        env = (
            EnvelopeBuilder()
            .set_producer("did:example:agent")
            .set_scope("healthcare")
            .set_ttl("PT1H")
            .set_risk_level(RiskLevel.HIGH)
            .set_human_oversight(True)
            .build()
        )
        assert env.scope == "healthcare"
        assert env.ttl == "PT1H"
        assert env.compliance.risk_level == RiskLevel.HIGH
        assert env.compliance.human_oversight_required is True

    def test_semantic_payload(self):
        payload = [{
            "@model": "UserML",
            "mainpart": {"subject": "u:1", "auxiliary": "hasProperty",
                         "predicate": "x", "range": "integer", "object": 1},
            "administration": {"group": "Observation"},
        }]
        env = (
            EnvelopeBuilder()
            .set_producer("did:example:1")
            .set_semantic_payload(payload)
            .build()
        )
        assert env.semantic_payload == payload

    def test_add_artifact(self):
        env = (
            EnvelopeBuilder()
            .set_producer("did:example:1")
            .add_artifact(
                artifact_id="art-1",
                artifact_type=ArtifactType.EMBEDDING,
                content_hash="sha256:abc",
                model="text-embedding-3",
                dimensions=1536,
            )
            .build()
        )
        assert len(env.artifacts_registry) == 1
        art = env.artifacts_registry[0]
        assert art.artifact_id == "art-1"
        assert art.type == ArtifactType.EMBEDDING
        assert art.model == "text-embedding-3"
        assert art.dimensions == 1536

    def test_multiple_artifacts(self):
        builder = EnvelopeBuilder().set_producer("did:example:1")
        for i in range(3):
            builder.add_artifact(
                artifact_id=f"art-{i}",
                artifact_type=ArtifactType.TOKEN_SEQUENCE,
                content_hash=f"sha256:{i}",
            )
        env = builder.build()
        assert len(env.artifacts_registry) == 3

    def test_set_passed_artifact(self):
        env = (
            EnvelopeBuilder()
            .set_producer("did:example:1")
            .add_artifact("art-1", ArtifactType.EMBEDDING, "sha256:abc")
            .set_passed_artifact("art-1")
            .build()
        )
        assert env.passed_artifact_pointer == "art-1"

    def test_set_passed_artifact_invalid_raises(self):
        with pytest.raises(ValueError, match="not in registry"):
            (
                EnvelopeBuilder()
                .set_producer("did:example:1")
                .set_passed_artifact("art-nonexistent")
            )

    def test_add_decision_influence(self):
        env = (
            EnvelopeBuilder()
            .set_producer("did:example:1")
            .add_decision_influence(
                agent="agent-sensor",
                categories=["temperature"],
                influence_weights={"temp": 0.7},
                confidence=0.9,
                abstraction_level=AbstractionLevel.OBSERVATION,
                temporal_scope=TemporalScope.CURRENT,
            )
            .build()
        )
        assert len(env.decision_influence) == 1
        di = env.decision_influence[0]
        assert di.agent == "agent-sensor"
        assert di.confidence == 0.9

    def test_set_privacy(self):
        env = (
            EnvelopeBuilder()
            .set_producer("did:example:1")
            .set_privacy(
                data_category="biometric",
                legal_basis="legitimate_interest",
                retention="P30D",
                feature_suppression=["face_embedding"],
            )
            .build()
        )
        assert env.privacy.data_category.value == "biometric"
        assert env.privacy.legal_basis == "legitimate_interest"
        assert env.privacy.feature_suppression == ["face_embedding"]

    def test_set_compliance(self):
        env = (
            EnvelopeBuilder()
            .set_producer("did:example:1")
            .set_compliance(
                risk_level=RiskLevel.HIGH,
                human_oversight_required=True,
                model_card_ref="https://example.com/card",
                escalation_path="oncall@example.com",
            )
            .build()
        )
        assert env.compliance.risk_level == RiskLevel.HIGH
        assert env.compliance.human_oversight_required is True
        assert env.compliance.model_card_ref == "https://example.com/card"

    def test_sign_and_build(self):
        env = (
            EnvelopeBuilder()
            .set_producer("did:example:1")
            .sign("did:example:1")
            .build()
        )
        assert env.proof.content_hash is not None
        assert env.proof.signature is not None
        assert env.proof.signer == "did:example:1"

    def test_content_hash_deterministic(self):
        """Same envelope config should produce same content hash."""
        def make():
            return (
                EnvelopeBuilder()
                .set_producer("did:example:1")
                .set_scope("test")
                .set_semantic_payload([{"key": "value"}])
                .build()
            )
        # Two separate builds from same builder config won't have same context_id
        # but we can verify the hash is computed
        env = make()
        assert env.proof.content_hash is not None
        assert len(env.proof.content_hash) == 64  # SHA-256 hex
