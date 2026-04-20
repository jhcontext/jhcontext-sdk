"""PAC-AI protocol data models (Pydantic v2)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ArtifactType(str, Enum):
    TOKEN_SEQUENCE = "token_sequence"
    EMBEDDING = "embedding"
    SEMANTIC_EXTRACTION = "semantic_extraction"
    TOOL_RESULT = "tool_result"
    AUDIO = "audio"
    IMAGE = "image"
    VIDEO = "video"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AbstractionLevel(str, Enum):
    OBSERVATION = "observation"
    INTERPRETATION = "interpretation"
    SITUATION = "situation"


class TemporalScope(str, Enum):
    CURRENT = "current"
    HISTORICAL = "historical"


class EnvelopeStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    DELETED = "deleted"


class ForwardingPolicy(str, Enum):
    SEMANTIC_FORWARD = "semantic_forward"  # Next consumer reads only semantic_payload
    RAW_FORWARD = "raw_forward"            # Next consumer reads full raw output

    def format_preamble(self, risk_level: str = "") -> str:
        """Generate task execution instructions from this policy.

        Returns a constraint string for SEMANTIC_FORWARD, empty for RAW_FORWARD.
        Agent runtimes prepend this to task descriptions.
        """
        if self == ForwardingPolicy.SEMANTIC_FORWARD:
            return (
                f"FORWARDING POLICY: SEMANTIC-FORWARD (risk_level={risk_level})\n"
                "You will receive a jhcontext protocol envelope. "
                "Read ONLY the `semantic_payload` field as your canonical input. "
                "Do NOT use raw tokens, embeddings, or any data outside the "
                "envelope's semantic_payload. This constraint ensures audit "
                "alignment — what you consume is exactly what the provenance "
                "graph records.\n\n"
            )
        return ""


class DataCategory(str, Enum):
    BEHAVIORAL = "behavioral"
    BIOMETRIC = "biometric"
    SENSITIVE = "sensitive"


# --- Component Models ---

class Artifact(BaseModel):
    artifact_id: str = Field(default_factory=lambda: f"art-{uuid.uuid4().hex[:8]}")
    type: ArtifactType
    storage_ref: str | None = None
    content_hash: str | None = None
    model: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    deterministic: bool = False
    confidence: float | None = None
    dimensions: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionInfluence(BaseModel):
    agent: str
    categories: list[str]
    abstraction_level: AbstractionLevel = AbstractionLevel.SITUATION
    temporal_scope: TemporalScope = TemporalScope.CURRENT
    influence_weights: dict[str, float] = Field(default_factory=dict)
    confidence: float = 0.0


class PrivacyBlock(BaseModel):
    data_category: DataCategory = DataCategory.BEHAVIORAL
    legal_basis: str = "consent"
    retention: str = "P7D"
    storage_policy: str = "centralized-encrypted"
    feature_suppression: list[str] = Field(default_factory=list)
    pii_detached: bool = False
    pii_vault_ref: str | None = None


class ComplianceBlock(BaseModel):
    risk_level: RiskLevel = RiskLevel.MEDIUM
    human_oversight_required: bool = False
    forwarding_policy: ForwardingPolicy = ForwardingPolicy.RAW_FORWARD
    model_card_ref: str | None = None
    test_suite_ref: str | None = None
    escalation_path: str | None = None


class ProvenanceRef(BaseModel):
    prov_graph_id: str | None = None
    prov_digest: str | None = None


class Proof(BaseModel):
    canonicalization: str = "URDNA2015"
    content_hash: str | None = None
    signature: str | None = None
    signer: str | None = None


# --- Main Envelope Model ---

class Envelope(BaseModel):
    context_id: str = Field(default_factory=lambda: f"ctx-{uuid.uuid4()}")
    schema_version: str = "jh:0.3"
    producer: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ttl: str = "PT30M"
    status: EnvelopeStatus = EnvelopeStatus.ACTIVE
    scope: str = ""

    semantic_payload: list[dict[str, Any]] = Field(default_factory=list)
    artifacts_registry: list[Artifact] = Field(default_factory=list)
    passed_artifact_pointer: str | None = None
    decision_influence: list[DecisionInfluence] = Field(default_factory=list)

    privacy: PrivacyBlock = Field(default_factory=PrivacyBlock)
    compliance: ComplianceBlock = Field(default_factory=ComplianceBlock)
    provenance_ref: ProvenanceRef = Field(default_factory=ProvenanceRef)
    proof: Proof = Field(default_factory=Proof)

    def to_jsonld(self, include_proof: bool = True) -> dict[str, Any]:
        """Serialize to JSON-LD format with @context and @type."""
        exclude = None if include_proof else {"proof"}
        d = self.model_dump(mode="json", exclude_none=True, exclude=exclude)
        d["@context"] = {
            "jh": "https://jhcontext.com/vocab#",
            "prov": "http://www.w3.org/ns/prov#",
            "xsd": "http://www.w3.org/2001/XMLSchema#",
        }
        d["@type"] = "jh:Envelope"
        return d


class Decision(BaseModel):
    decision_id: str = Field(default_factory=lambda: f"dec-{uuid.uuid4().hex[:8]}")
    context_id: str
    passed_artifact_id: str | None = None
    outcome: dict[str, Any] = Field(default_factory=dict)
    agent_id: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
