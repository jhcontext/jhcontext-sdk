"""Step persistence for multi-task pipelines.

Framework-agnostic — no CrewAI imports. Orchestrates envelope extension,
PROV graph updates, and API persistence for individual pipeline steps.
"""

from __future__ import annotations

import time
from typing import Any

from .builder import EnvelopeBuilder
from .crypto import compute_sha256
from .models import ArtifactType
from .prov import PROVGraph

LARGE_ARTIFACT_THRESHOLD = 100_000  # 100 KB


class StepPersister:
    """Persists pipeline steps as auditable artifacts in PAC-AI envelopes.

    Manages the lifecycle of extending an envelope with new artifacts,
    updating the W3C PROV graph with provenance relations, and submitting
    both to the backend API.

    Usage::

        from jhcontext import EnvelopeBuilder, PROVGraph
        from jhcontext.client.api_client import JHContextClient
        from jhcontext.persistence import StepPersister

        persister = StepPersister(
            client=JHContextClient(base_url="http://localhost:8400"),
            builder=builder,
            prov=prov,
            context_id="ctx-abc123",
        )

        artifact_id = persister.persist(
            step_name="sensor",
            agent_id="did:hospital:sensor-agent",
            output="raw sensor data...",
            artifact_type=ArtifactType.TOKEN_SEQUENCE,
            started_at="2026-03-23T10:00:00Z",
            ended_at="2026-03-23T10:01:00Z",
            used_artifacts=None,
        )
    """

    def __init__(
        self,
        client: Any,  # JHContextClient — typed as Any to avoid circular import
        builder: EnvelopeBuilder,
        prov: PROVGraph,
        context_id: str,
    ) -> None:
        self.client = client
        self.builder = builder
        self.prov = prov
        self.context_id = context_id
        self.step_artifacts: list[str] = []
        self.metrics: list[dict[str, Any]] = []

    def persist(
        self,
        step_name: str,
        agent_id: str,
        output: str,
        artifact_type: ArtifactType,
        started_at: str,
        ended_at: str,
        used_artifacts: list[str] | None = None,
    ) -> str:
        """Persist a single step — extends envelope + PROV, submits to API.

        Returns the artifact_id of the persisted step.
        """
        t0 = time.time()

        content = output.encode("utf-8")
        content_hash = compute_sha256(content)
        artifact_id = f"art-{step_name}"

        # Upload large artifacts to S3
        storage_ref = None
        if len(content) > LARGE_ARTIFACT_THRESHOLD:
            resp = self.client.upload_artifact(
                artifact_id=artifact_id,
                context_id=self.context_id,
                artifact_type=artifact_type.value,
                content=content,
            )
            storage_ref = resp.get("storage_path")

        # Extend envelope
        self.builder.add_artifact(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            content_hash=content_hash,
            storage_ref=storage_ref,
        )
        self.builder.set_passed_artifact(artifact_id)

        # Extend PROV graph
        self.prov.add_agent(agent_id, agent_id, role=step_name)
        self.prov.add_entity(
            artifact_id,
            f"Output of {step_name}",
            artifact_type=artifact_type.value,
            content_hash=content_hash,
        )
        activity_id = f"act-{step_name}"
        self.prov.add_activity(
            activity_id, step_name, started_at=started_at, ended_at=ended_at
        )
        self.prov.was_generated_by(artifact_id, activity_id)
        self.prov.was_associated_with(activity_id, agent_id)

        if used_artifacts:
            for used in used_artifacts:
                self.prov.used(activity_id, used)
                self.prov.was_derived_from(artifact_id, used)

        # Sign and persist
        env = self.builder.sign(agent_id).build()
        self.client.submit_envelope(env)
        self.client.submit_prov_graph(self.context_id, self.prov.serialize("turtle"))

        # Track
        self.step_artifacts.append(artifact_id)
        persist_ms = (time.time() - t0) * 1000
        self.metrics.append(
            {
                "step": step_name,
                "agent": agent_id,
                "artifact_id": artifact_id,
                "content_size_bytes": len(content),
                "persist_ms": round(persist_ms, 2),
                "started_at": started_at,
                "ended_at": ended_at,
            }
        )

        return artifact_id

    def finalize_metrics(self, total_start: float) -> dict[str, Any]:
        """Compute final metrics including total elapsed time."""
        return {
            "context_id": self.context_id,
            "total_ms": round((time.time() - total_start) * 1000, 2),
            "steps": list(self.metrics),
        }
