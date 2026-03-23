"""jhcontext — PAC-AI: Protocol for Auditable Context in AI.

Install modes:
  pip install jhcontext              # Client + core (models, builder, prov, audit)
  pip install jhcontext[server]      # + Server (FastAPI, MCP, SQLite)
  pip install jhcontext[crewai]      # + CrewAI integration
  pip install jhcontext[all]         # Everything
"""

from .models import (
    Artifact,
    ArtifactType,
    ComplianceBlock,
    Decision,
    DecisionInfluence,
    Envelope,
    EnvelopeStatus,
    ForwardingPolicy,
    PrivacyBlock,
    Proof,
    ProvenanceRef,
    RiskLevel,
    AbstractionLevel,
    TemporalScope,
    DataCategory,
)
from .builder import EnvelopeBuilder
from .prov import PROVGraph
from .audit import (
    AuditReport,
    AuditResult,
    generate_audit_report,
    verify_integrity,
    verify_negative_proof,
    verify_pii_detachment,
    verify_temporal_oversight,
    verify_workflow_isolation,
)
from .pii import (
    DefaultPIIDetector,
    InMemoryPIIVault,
    PIIDetector,
    PIIMatch,
    PIIVault,
    detach_pii,
    is_pii_token,
    reattach_pii,
    tokenize_value,
)
from .crypto import compute_sha256, compute_content_hash, sign_envelope, verify_envelope
from .canonicalize import canonicalize
from .semantics import observation, interpretation, situation, userml_payload
from .forwarding import ForwardingEnforcer
from .persistence import StepPersister

__version__ = "0.3.0"

__all__ = [
    # Models
    "Artifact", "ArtifactType", "ComplianceBlock", "Decision", "DecisionInfluence",
    "Envelope", "EnvelopeStatus", "ForwardingPolicy", "PrivacyBlock", "Proof",
    "ProvenanceRef", "RiskLevel", "AbstractionLevel", "TemporalScope", "DataCategory",
    # Builder
    "EnvelopeBuilder",
    # PROV
    "PROVGraph",
    # Audit
    "AuditReport", "AuditResult", "generate_audit_report",
    "verify_integrity", "verify_negative_proof", "verify_pii_detachment",
    "verify_temporal_oversight", "verify_workflow_isolation",
    # PII
    "DefaultPIIDetector", "InMemoryPIIVault", "PIIDetector", "PIIMatch", "PIIVault",
    "detach_pii", "is_pii_token", "reattach_pii", "tokenize_value",
    # Crypto
    "compute_sha256", "compute_content_hash", "sign_envelope", "verify_envelope",
    # Forwarding & Persistence
    "ForwardingEnforcer", "StepPersister",
    # Utilities
    "canonicalize", "observation", "interpretation", "situation", "userml_payload",
]
