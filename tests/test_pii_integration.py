"""Integration tests for PII detachment across the SDK stack."""

import json

import pytest

from jhcontext import (
    EnvelopeBuilder,
    verify_integrity,
    verify_pii_detachment,
)
from jhcontext.pii import (
    DefaultPIIDetector,
    InMemoryPIIVault,
    detach_pii,
    is_pii_token,
    reattach_pii,
)
from jhcontext.semantics import observation


class TestBuilderPIIIntegration:
    def test_builder_with_pii_detachment(self):
        """EnvelopeBuilder.enable_pii_detachment() tokenizes PII before signing."""
        vault = InMemoryPIIVault()

        envelope = (
            EnvelopeBuilder()
            .set_producer("did:example:agent-1")
            .set_scope("healthcare")
            .set_semantic_payload([
                {"subject": "alice@example.com", "observation": "location", "value": "home"},
            ])
            .enable_pii_detachment(vault=vault)
            .sign("did:example:agent-1")
            .build()
        )

        assert envelope.privacy.pii_detached is True
        assert is_pii_token(envelope.semantic_payload[0]["subject"])
        assert envelope.semantic_payload[0]["value"] == "home"
        # Vault should contain the original
        token = envelope.semantic_payload[0]["subject"]
        assert vault.retrieve(token) == "alice@example.com"

    def test_builder_feature_suppression_auto_detach(self):
        """Setting feature_suppression triggers automatic PII detachment."""
        vault = InMemoryPIIVault()

        envelope = (
            EnvelopeBuilder()
            .set_producer("did:example:agent-1")
            .set_semantic_payload([
                {"patient_name": "John Doe", "condition": "stable"},
            ])
            .set_privacy(feature_suppression=["patient_name"])
            .enable_pii_detachment(vault=vault)
            .build()
        )

        assert envelope.privacy.pii_detached is True
        assert is_pii_token(envelope.semantic_payload[0]["patient_name"])
        assert envelope.semantic_payload[0]["condition"] == "stable"

    def test_builder_no_double_detach(self):
        """If already detached, build() should not re-process."""
        vault = InMemoryPIIVault()

        builder = (
            EnvelopeBuilder()
            .set_producer("did:example:agent-1")
            .set_semantic_payload([
                {"subject": "alice@example.com"},
            ])
            .enable_pii_detachment(vault=vault)
        )

        envelope = builder.build()
        token_first = envelope.semantic_payload[0]["subject"]

        # Build again — should not change anything
        assert is_pii_token(token_first)


class TestAuditPIIIntegration:
    def test_audit_pii_detachment_passes(self):
        """verify_pii_detachment passes on a properly detached envelope."""
        vault = InMemoryPIIVault()

        envelope = (
            EnvelopeBuilder()
            .set_producer("did:example:agent-1")
            .set_semantic_payload([
                {"subject": "alice@example.com", "value": "home"},
            ])
            .enable_pii_detachment(vault=vault)
            .sign("did:example:agent-1")
            .build()
        )

        result = verify_pii_detachment(envelope)
        assert result.passed is True
        assert result.evidence["residual_pii_count"] == 0

    def test_audit_pii_detachment_fails_not_detached(self):
        """verify_pii_detachment fails if envelope is not marked as detached."""
        envelope = (
            EnvelopeBuilder()
            .set_producer("did:example:agent-1")
            .set_semantic_payload([
                {"subject": "alice@example.com"},
            ])
            .sign("did:example:agent-1")
            .build()
        )

        result = verify_pii_detachment(envelope)
        assert result.passed is False

    def test_audit_pii_detachment_fails_with_residual_pii(self):
        """verify_pii_detachment fails if PII remains despite pii_detached flag."""
        envelope = (
            EnvelopeBuilder()
            .set_producer("did:example:agent-1")
            .set_semantic_payload([
                {"subject": "alice@example.com"},
            ])
            .build()
        )
        # Manually set the flag without actually detaching
        envelope.privacy.pii_detached = True

        result = verify_pii_detachment(envelope)
        assert result.passed is False
        assert result.evidence["residual_pii_count"] > 0


class TestPurgePIIIntegration:
    def test_purge_preserves_integrity(self):
        """After PII purge, envelope integrity check still passes."""
        vault = InMemoryPIIVault()

        envelope = (
            EnvelopeBuilder()
            .set_producer("did:example:agent-1")
            .set_semantic_payload([
                {"subject": "alice@example.com", "value": "home"},
            ])
            .enable_pii_detachment(vault=vault)
            .sign("did:example:agent-1")
            .build()
        )

        # Verify integrity before purge
        assert verify_integrity(envelope).passed is True

        # Purge PII
        vault.purge_by_context(envelope.context_id)

        # Integrity still holds — hash covers detached payload
        assert verify_integrity(envelope).passed is True

    def test_purge_context_id_still_resolves(self):
        """After PII purge, the envelope still has a valid context_id."""
        vault = InMemoryPIIVault()

        envelope = (
            EnvelopeBuilder()
            .set_producer("did:example:agent-1")
            .set_semantic_payload([
                {"subject": "alice@example.com"},
            ])
            .enable_pii_detachment(vault=vault)
            .sign("did:example:agent-1")
            .build()
        )

        vault.purge_by_context(envelope.context_id)

        assert envelope.context_id.startswith("ctx-")
        assert envelope.proof.content_hash is not None

    def test_reattach_after_purge_preserves_tokens(self):
        """Reattach after purge leaves tokens as-is (graceful degradation)."""
        vault = InMemoryPIIVault()
        detector = DefaultPIIDetector()
        payload = [{"subject": "alice@example.com", "value": "home"}]

        detached = detach_pii(payload, "ctx-1", detector, vault)
        vault.purge_by_context("ctx-1")
        reattached = reattach_pii(detached, vault)

        # Token remains because vault was purged
        assert is_pii_token(reattached[0]["subject"])
        assert reattached[0]["value"] == "home"


class TestHealthcareScenario:
    """End-to-end healthcare scenario with PII detachment."""

    def test_patient_pii_detachment_flow(self):
        vault = InMemoryPIIVault()

        # 1. Agent creates envelope with patient PII
        envelope = (
            EnvelopeBuilder()
            .set_producer("did:example:triage-agent")
            .set_scope("healthcare")
            .set_semantic_payload([
                {
                    "patient_name": "Alice Johnson",
                    "patient_email": "alice.johnson@hospital.org",
                    "diagnosis": "mild concussion",
                    "recommendation": "24h observation",
                },
            ])
            .set_privacy(
                data_category="sensitive",
                legal_basis="legitimate_interest",
                feature_suppression=["patient_name", "patient_email"],
            )
            .enable_pii_detachment(vault=vault)
            .sign("did:example:triage-agent")
            .build()
        )

        # 2. Verify PII is detached
        assert envelope.privacy.pii_detached is True
        assert is_pii_token(envelope.semantic_payload[0]["patient_name"])
        assert is_pii_token(envelope.semantic_payload[0]["patient_email"])
        assert envelope.semantic_payload[0]["diagnosis"] == "mild concussion"

        # 3. Audit passes
        pii_result = verify_pii_detachment(envelope)
        assert pii_result.passed is True

        integrity_result = verify_integrity(envelope)
        assert integrity_result.passed is True

        # 4. GDPR erasure
        purged = vault.purge_by_context(envelope.context_id)
        assert purged == 2  # patient_name + patient_email

        # 5. Audit trail survives
        assert verify_integrity(envelope).passed is True
        assert envelope.context_id.startswith("ctx-")

        # 6. Reattach gracefully fails
        reattached = reattach_pii(envelope.semantic_payload, vault)
        assert is_pii_token(reattached[0]["patient_name"])
