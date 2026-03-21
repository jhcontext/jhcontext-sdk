"""Tests for jhcontext.audit — compliance verification utilities."""

import pytest
from jhcontext.audit import (
    AuditReport,
    AuditResult,
    generate_audit_report,
    verify_integrity,
    verify_negative_proof,
    verify_temporal_oversight,
    verify_workflow_isolation,
)
from jhcontext.builder import EnvelopeBuilder
from jhcontext.models import RiskLevel
from jhcontext.prov import PROVGraph


class TestAuditResult:
    def test_creation(self):
        r = AuditResult(check_name="test", passed=True, message="ok")
        assert r.check_name == "test"
        assert r.passed is True
        assert r.evidence == {}

    def test_with_evidence(self):
        r = AuditResult(
            check_name="test",
            passed=False,
            evidence={"key": "value"},
            message="failed",
        )
        assert r.evidence["key"] == "value"


class TestAuditReport:
    def test_to_dict(self):
        results = [
            AuditResult("check1", True, message="ok"),
            AuditResult("check2", False, message="fail"),
        ]
        report = AuditReport(
            context_id="ctx-1",
            results=results,
            overall_passed=False,
        )
        d = report.to_dict()
        assert d["context_id"] == "ctx-1"
        assert d["overall_passed"] is False
        assert len(d["results"]) == 2
        assert d["results"][0]["check_name"] == "check1"


class TestVerifyTemporalOversight:
    @pytest.fixture
    def prov_with_oversight(self):
        """PROV graph where doctor reviews AFTER AI analysis for >= 5 min."""
        pg = PROVGraph("ctx-health")
        pg.add_activity("ai-analysis", "AI Analysis",
                        started_at="2026-01-01T10:00:00",
                        ended_at="2026-01-01T10:01:00")
        pg.add_activity("doctor-review", "Doctor Review",
                        started_at="2026-01-01T10:05:00",
                        ended_at="2026-01-01T10:15:00")  # 10 min review
        return pg

    def test_passes_with_sufficient_oversight(self, prov_with_oversight):
        result = verify_temporal_oversight(
            prov_with_oversight,
            ai_activity_id="ai-analysis",
            human_activities=["doctor-review"],
            min_review_seconds=300.0,  # 5 min
        )
        assert result.passed is True
        assert result.check_name == "temporal_oversight"
        assert result.evidence["total_review_seconds"] == 600.0  # 10 min

    def test_fails_insufficient_review_time(self):
        pg = PROVGraph()
        pg.add_activity("ai", "AI",
                        started_at="2026-01-01T10:00:00",
                        ended_at="2026-01-01T10:01:00")
        pg.add_activity("human", "Human Review",
                        started_at="2026-01-01T10:02:00",
                        ended_at="2026-01-01T10:03:00")  # only 1 min
        result = verify_temporal_oversight(pg, "ai", ["human"], min_review_seconds=300)
        assert result.passed is False

    def test_fails_human_before_ai(self):
        pg = PROVGraph()
        pg.add_activity("ai", "AI",
                        started_at="2026-01-01T10:30:00",
                        ended_at="2026-01-01T10:31:00")
        pg.add_activity("human", "Human",
                        started_at="2026-01-01T10:00:00",
                        ended_at="2026-01-01T10:10:00")  # before AI
        result = verify_temporal_oversight(pg, "ai", ["human"], min_review_seconds=60)
        assert result.passed is False

    def test_fails_missing_ai_activity(self):
        pg = PROVGraph()
        pg.add_activity("human", "Human",
                        started_at="2026-01-01T10:00:00",
                        ended_at="2026-01-01T10:10:00")
        result = verify_temporal_oversight(pg, "nonexistent", ["human"])
        assert result.passed is False
        assert "not found" in result.message


class TestVerifyNegativeProof:
    @pytest.fixture
    def education_prov(self):
        """Education scenario: grading uses academic data only."""
        pg = PROVGraph("ctx-edu")
        pg.add_entity("grades", "Academic Grades", artifact_type="token_sequence")
        pg.add_entity("attendance", "Attendance Records", artifact_type="token_sequence")
        pg.add_entity("decision", "Final Grade")
        pg.add_activity("grading", "Grading Process")
        pg.used("grading", "grades")
        pg.used("grading", "attendance")
        pg.was_generated_by("decision", "grading")
        pg.was_derived_from("decision", "grades")
        return pg

    def test_passes_no_excluded_types(self, education_prov):
        result = verify_negative_proof(
            education_prov,
            decision_entity_id="decision",
            excluded_artifact_types=["biometric", "social_media"],
        )
        assert result.passed is True
        assert result.evidence["violations"] == []

    def test_fails_with_excluded_type_in_chain(self):
        pg = PROVGraph()
        pg.add_entity("biometric-data", "Face Scan", artifact_type="biometric")
        pg.add_entity("decision", "Final Grade")
        pg.was_derived_from("decision", "biometric-data")
        result = verify_negative_proof(pg, "decision", ["biometric"])
        assert result.passed is False
        assert len(result.evidence["violations"]) == 1

    def test_empty_chain(self):
        pg = PROVGraph()
        pg.add_entity("decision", "Isolated Decision")
        result = verify_negative_proof(pg, "decision", ["biometric"])
        assert result.passed is True


class TestVerifyWorkflowIsolation:
    def test_isolated_workflows(self):
        prov_a = PROVGraph()
        prov_a.add_entity("a1", "Entity A1")
        prov_a.add_entity("a2", "Entity A2")

        prov_b = PROVGraph()
        prov_b.add_entity("b1", "Entity B1")

        result = verify_workflow_isolation(prov_a, prov_b)
        assert result.passed is True
        assert result.evidence["shared_entities"] == []

    def test_shared_entities_fail(self):
        prov_a = PROVGraph()
        prov_a.add_entity("shared", "Shared Entity")
        prov_a.add_entity("a1", "Entity A")

        prov_b = PROVGraph()
        prov_b.add_entity("shared", "Shared Entity")
        prov_b.add_entity("b1", "Entity B")

        result = verify_workflow_isolation(prov_a, prov_b)
        assert result.passed is False
        assert len(result.evidence["shared_entities"]) == 1

    def test_empty_workflows(self):
        result = verify_workflow_isolation(PROVGraph(), PROVGraph())
        assert result.passed is True


class TestVerifyIntegrity:
    def test_signed_envelope_passes(self):
        env = (
            EnvelopeBuilder()
            .set_producer("did:example:1")
            .set_scope("test")
            .sign("did:example:1")
            .build()
        )
        result = verify_integrity(env)
        assert result.passed is True

    def test_unsigned_envelope_fails(self):
        env = EnvelopeBuilder().set_producer("did:example:1").build()
        result = verify_integrity(env)
        assert result.passed is False

    def test_tampered_envelope_fails(self):
        env = (
            EnvelopeBuilder()
            .set_producer("did:example:1")
            .sign("did:example:1")
            .build()
        )
        # Tamper with the envelope after signing
        env.scope = "tampered"
        result = verify_integrity(env)
        assert result.passed is False


class TestGenerateAuditReport:
    def test_all_pass(self):
        env = EnvelopeBuilder().set_producer("did:example:1").build()
        prov = PROVGraph()
        results = [
            AuditResult("check1", True),
            AuditResult("check2", True),
        ]
        report = generate_audit_report(env, prov, results)
        assert report.overall_passed is True
        assert report.context_id == env.context_id

    def test_one_fails(self):
        env = EnvelopeBuilder().set_producer("did:example:1").build()
        prov = PROVGraph()
        results = [
            AuditResult("check1", True),
            AuditResult("check2", False),
        ]
        report = generate_audit_report(env, prov, results)
        assert report.overall_passed is False
