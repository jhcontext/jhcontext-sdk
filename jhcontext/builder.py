"""Fluent builder for PAC-AI envelopes."""

from __future__ import annotations

from typing import Any

from .models import (
    Artifact,
    ArtifactType,
    ComplianceBlock,
    DecisionInfluence,
    Envelope,
    PrivacyBlock,
    RiskLevel,
    AbstractionLevel,
    TemporalScope,
)
from .crypto import compute_sha256
from .canonicalize import canonicalize


class EnvelopeBuilder:
    """Fluent API for constructing PAC-AI envelopes."""

    def __init__(self) -> None:
        self._envelope = Envelope()

    def set_producer(self, producer_did: str) -> EnvelopeBuilder:
        self._envelope.producer = producer_did
        return self

    def set_scope(self, scope: str) -> EnvelopeBuilder:
        self._envelope.scope = scope
        return self

    def set_ttl(self, ttl: str) -> EnvelopeBuilder:
        self._envelope.ttl = ttl
        return self

    def set_risk_level(self, level: RiskLevel) -> EnvelopeBuilder:
        self._envelope.compliance.risk_level = level
        return self

    def set_human_oversight(self, required: bool) -> EnvelopeBuilder:
        self._envelope.compliance.human_oversight_required = required
        return self

    def set_semantic_payload(self, payload: list[dict[str, Any]]) -> EnvelopeBuilder:
        self._envelope.semantic_payload = payload
        return self

    def add_artifact(
        self,
        artifact_id: str,
        artifact_type: ArtifactType,
        content_hash: str,
        model: str | None = None,
        deterministic: bool = False,
        confidence: float | None = None,
        dimensions: int | None = None,
        storage_ref: str | None = None,
        **metadata: Any,
    ) -> EnvelopeBuilder:
        artifact = Artifact(
            artifact_id=artifact_id,
            type=artifact_type,
            content_hash=content_hash,
            model=model,
            deterministic=deterministic,
            confidence=confidence,
            dimensions=dimensions,
            storage_ref=storage_ref,
            metadata=metadata,
        )
        self._envelope.artifacts_registry.append(artifact)
        return self

    def set_passed_artifact(self, artifact_id: str) -> EnvelopeBuilder:
        ids = [a.artifact_id for a in self._envelope.artifacts_registry]
        if artifact_id not in ids:
            raise ValueError(
                f"Artifact '{artifact_id}' not in registry. Available: {ids}"
            )
        self._envelope.passed_artifact_pointer = artifact_id
        return self

    def add_decision_influence(
        self,
        agent: str,
        categories: list[str],
        influence_weights: dict[str, float],
        confidence: float = 0.0,
        abstraction_level: AbstractionLevel = AbstractionLevel.SITUATION,
        temporal_scope: TemporalScope = TemporalScope.CURRENT,
    ) -> EnvelopeBuilder:
        di = DecisionInfluence(
            agent=agent,
            categories=categories,
            abstraction_level=abstraction_level,
            temporal_scope=temporal_scope,
            influence_weights=influence_weights,
            confidence=confidence,
        )
        self._envelope.decision_influence.append(di)
        return self

    def set_privacy(
        self,
        data_category: str = "behavioral",
        legal_basis: str = "consent",
        retention: str = "P7D",
        storage_policy: str = "centralized-encrypted",
        feature_suppression: list[str] | None = None,
    ) -> EnvelopeBuilder:
        self._envelope.privacy = PrivacyBlock(
            data_category=data_category,
            legal_basis=legal_basis,
            retention=retention,
            storage_policy=storage_policy,
            feature_suppression=feature_suppression or [],
        )
        return self

    def set_compliance(
        self,
        risk_level: RiskLevel = RiskLevel.MEDIUM,
        human_oversight_required: bool = False,
        model_card_ref: str | None = None,
        test_suite_ref: str | None = None,
        escalation_path: str | None = None,
    ) -> EnvelopeBuilder:
        self._envelope.compliance = ComplianceBlock(
            risk_level=risk_level,
            human_oversight_required=human_oversight_required,
            model_card_ref=model_card_ref,
            test_suite_ref=test_suite_ref,
            escalation_path=escalation_path,
        )
        return self

    def sign(self, signer_did: str) -> EnvelopeBuilder:
        from .crypto import sign_envelope
        self._envelope.proof = sign_envelope(self._envelope, signer_did)
        return self

    def build(self) -> Envelope:
        """Build and return the envelope. Computes content hash if not signed."""
        if not self._envelope.proof.content_hash:
            canonical = canonicalize(self._envelope.to_jsonld(include_proof=False))
            self._envelope.proof.content_hash = compute_sha256(
                canonical.encode("utf-8")
            )
        return self._envelope
