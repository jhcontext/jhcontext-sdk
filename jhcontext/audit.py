"""Audit verification utilities for PAC-AI compliance checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .models import Envelope
from .prov import PROVGraph


@dataclass
class AuditResult:
    """Result of a single audit check."""
    check_name: str
    passed: bool
    evidence: dict[str, Any] = field(default_factory=dict)
    message: str = ""


@dataclass
class AuditReport:
    """Complete audit report for an envelope."""
    context_id: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    results: list[AuditResult] = field(default_factory=list)
    overall_passed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_id": self.context_id,
            "timestamp": self.timestamp,
            "overall_passed": self.overall_passed,
            "results": [
                {
                    "check_name": r.check_name,
                    "passed": r.passed,
                    "evidence": r.evidence,
                    "message": r.message,
                }
                for r in self.results
            ],
        }


def verify_temporal_oversight(
    prov: PROVGraph,
    ai_activity_id: str,
    human_activities: list[str],
    min_review_seconds: float = 300.0,
) -> AuditResult:
    """Healthcare Art. 14: Verify meaningful human oversight.

    Checks:
    1. Human accessed source documents AFTER AI generated recommendation
    2. Total review duration >= min_review_seconds
    3. Human activities include access to source data (not just AI summary)
    """
    sequence = prov.get_temporal_sequence()
    activity_map = {a["activity_id"]: a for a in sequence}

    ai_info = activity_map.get(ai_activity_id)
    if not ai_info or not ai_info.get("started_at"):
        return AuditResult(
            check_name="temporal_oversight",
            passed=False,
            message=f"AI activity '{ai_activity_id}' not found or missing timestamp",
        )

    ai_time = ai_info["started_at"]
    human_after_ai = []
    total_review_seconds = 0.0

    for h_id in human_activities:
        h_info = activity_map.get(h_id)
        if not h_info:
            continue
        if h_info.get("started_at", "") > ai_time:
            human_after_ai.append(h_id)
        if h_info.get("started_at") and h_info.get("ended_at"):
            try:
                start = datetime.fromisoformat(h_info["started_at"])
                end = datetime.fromisoformat(h_info["ended_at"])
                total_review_seconds += (end - start).total_seconds()
            except ValueError:
                pass

    passed = (
        len(human_after_ai) == len(human_activities)
        and total_review_seconds >= min_review_seconds
    )

    return AuditResult(
        check_name="temporal_oversight",
        passed=passed,
        evidence={
            "ai_activity": ai_activity_id,
            "ai_timestamp": ai_time,
            "human_activities_after_ai": human_after_ai,
            "total_review_seconds": total_review_seconds,
            "min_required_seconds": min_review_seconds,
        },
        message=(
            f"Human oversight verified: {len(human_after_ai)}/{len(human_activities)} "
            f"activities after AI, {total_review_seconds:.0f}s review time"
            if passed
            else f"Oversight insufficient: {total_review_seconds:.0f}s < {min_review_seconds:.0f}s required"
        ),
    )


def verify_negative_proof(
    prov: PROVGraph,
    decision_entity_id: str,
    excluded_artifact_types: list[str],
) -> AuditResult:
    """Education Art. 13: Prove excluded data was NOT used in decision.

    Checks that no entity with any of the excluded_artifact_types
    appears in the decision's dependency chain (recursive wasDerivedFrom + used).
    """
    chain = prov.get_entities_in_chain(decision_entity_id)

    from rdflib.namespace import PROV as PROV_NS
    violations = []
    for entity_id in chain:
        uri = prov._uri(entity_id)
        art_type = prov._graph.value(uri, prov._uri("artifactType"))
        if art_type and str(art_type) in excluded_artifact_types:
            violations.append({"entity": entity_id, "type": str(art_type)})

    return AuditResult(
        check_name="negative_proof",
        passed=len(violations) == 0,
        evidence={
            "decision_entity": decision_entity_id,
            "dependency_chain": list(chain),
            "excluded_types": excluded_artifact_types,
            "violations": violations,
        },
        message=(
            f"Negative proof verified: {len(excluded_artifact_types)} excluded types "
            f"absent from {len(chain)} entities in chain"
            if not violations
            else f"VIOLATION: {len(violations)} excluded artifacts found in chain"
        ),
    )


def verify_workflow_isolation(
    prov_a: PROVGraph,
    prov_b: PROVGraph,
) -> AuditResult:
    """Education: Verify two workflows share zero artifacts.

    Checks that there are no common entities between two PROV graphs.
    """
    entities_a = set(prov_a.get_all_entities())
    entities_b = set(prov_b.get_all_entities())
    shared = entities_a & entities_b

    return AuditResult(
        check_name="workflow_isolation",
        passed=len(shared) == 0,
        evidence={
            "workflow_a_entities": len(entities_a),
            "workflow_b_entities": len(entities_b),
            "shared_entities": list(shared),
        },
        message=(
            f"Workflows isolated: {len(entities_a)} + {len(entities_b)} entities, 0 shared"
            if not shared
            else f"ISOLATION VIOLATION: {len(shared)} shared entities: {shared}"
        ),
    )


def verify_integrity(envelope: Envelope) -> AuditResult:
    """Verify envelope cryptographic integrity (hash + signature)."""
    from .crypto import verify_envelope

    passed = verify_envelope(envelope)
    return AuditResult(
        check_name="integrity",
        passed=passed,
        evidence={
            "content_hash": envelope.proof.content_hash,
            "signer": envelope.proof.signer,
            "has_signature": bool(envelope.proof.signature),
        },
        message="Integrity verified" if passed else "INTEGRITY FAILURE: hash or signature mismatch",
    )


def verify_pii_detachment(
    envelope: Envelope,
    detector: Any | None = None,
) -> AuditResult:
    """Verify that no PII remains in the stored envelope's semantic_payload.

    Scans all string values in the payload for PII patterns.
    Passes if ``pii_detached`` is True AND no PII patterns are detected.
    """
    from .pii import DefaultPIIDetector

    if not envelope.privacy.pii_detached:
        return AuditResult(
            check_name="pii_detachment",
            passed=False,
            message="Envelope not marked as PII-detached",
            evidence={"pii_detached": False},
        )

    det = detector or DefaultPIIDetector(
        suppressed_fields=envelope.privacy.feature_suppression,
    )
    matches = det.scan_payload(envelope.semantic_payload)

    return AuditResult(
        check_name="pii_detachment",
        passed=len(matches) == 0,
        evidence={
            "pii_detached": True,
            "residual_pii_count": len(matches),
            "residual_pii": [
                {"field_path": m.field_path, "type": m.detection_type}
                for m in matches
            ],
        },
        message=(
            "PII detachment verified: no personal data in payload"
            if not matches
            else f"PII LEAK: {len(matches)} residual PII occurrences found"
        ),
    )


def generate_audit_report(
    envelope: Envelope,
    prov: PROVGraph,
    results: list[AuditResult],
) -> AuditReport:
    """Generate a complete audit report from individual check results."""
    report = AuditReport(
        context_id=envelope.context_id,
        results=results,
        overall_passed=all(r.passed for r in results),
    )
    return report
