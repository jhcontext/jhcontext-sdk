"""Flat Envelope model for LLM structured output.

The full ``Envelope`` pydantic model has deeply nested types that exceed
Anthropic's structured output grammar size limit.  ``FlatEnvelope``
uses only scalar fields and simple lists (no nested dicts/objects) so
it works with any LLM's structured output grammar, including Haiku.

The ``to_envelope()`` method converts back to a full ``Envelope``.

Usage with CrewAI::

    from jhcontext.flat_envelope import FlatEnvelope

    @task
    def sensor_task(self) -> Task:
        return Task(
            config=self.tasks_config["sensor_task"],
            output_pydantic=FlatEnvelope,
        )

    # In the callback, convert to full Envelope:
    flat: FlatEnvelope = output.pydantic
    envelope: Envelope = flat.to_envelope()
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from pydantic import BaseModel, Field

from .models import (
    Artifact,
    ArtifactType,
    ComplianceBlock,
    DecisionInfluence,
    Envelope,
    ForwardingPolicy,
    RiskLevel,
)


class FlatEnvelope(BaseModel):
    """Flat (scalar-only) envelope for LLM structured output.

    All nested blocks are promoted to top-level scalar fields.
    Complex data (semantic_payload, influence_weights) is stored as
    JSON strings to avoid nested object schemas.

    Call ``to_envelope()`` to convert to the full protocol ``Envelope``.
    """

    # ── Identity ─────────────────────────────────────────────────
    producer: str = ""
    scope: str = ""

    # ── Semantic payload as JSON string ──────────────────────────
    # The LLM writes its semantic payload as a JSON string.
    # to_envelope() parses it back to list[dict].
    semantic_payload_json: str = "[]"

    # ── Artifact (single, flattened) ─────────────────────────────
    artifact_id: str = Field(default_factory=lambda: f"art-{uuid.uuid4().hex[:8]}")
    artifact_type: str = "semantic_extraction"

    # ── Decision influence (flattened scalars) ───────────────────
    di_agent: str = ""
    di_categories: list[str] = Field(default_factory=list)

    # ── Compliance (flattened scalars) ───────────────────────────
    risk_level: str = "medium"
    human_oversight_required: bool = False
    forwarding_policy: str = "raw_forward"

    def to_envelope(self) -> Envelope:
        """Convert this flat representation to a full protocol Envelope."""
        # Parse semantic payload
        try:
            payload = json.loads(self.semantic_payload_json)
            if not isinstance(payload, list):
                payload = [payload] if isinstance(payload, dict) else []
        except (json.JSONDecodeError, TypeError):
            payload = []

        # Map artifact type
        try:
            art_type = ArtifactType(self.artifact_type)
        except ValueError:
            art_type = ArtifactType.SEMANTIC_EXTRACTION

        artifacts = [
            Artifact(
                artifact_id=self.artifact_id,
                type=art_type,
            )
        ]

        decision_influence = []
        if self.di_agent and self.di_categories:
            decision_influence.append(
                DecisionInfluence(
                    agent=self.di_agent,
                    categories=self.di_categories,
                )
            )

        try:
            risk = RiskLevel(self.risk_level)
        except ValueError:
            risk = RiskLevel.MEDIUM

        try:
            fwd = ForwardingPolicy(self.forwarding_policy)
        except ValueError:
            fwd = ForwardingPolicy.RAW_FORWARD

        return Envelope(
            producer=self.producer,
            scope=self.scope,
            semantic_payload=payload,
            artifacts_registry=artifacts,
            decision_influence=decision_influence,
            compliance=ComplianceBlock(
                risk_level=risk,
                human_oversight_required=self.human_oversight_required,
                forwarding_policy=fwd,
            ),
        )
