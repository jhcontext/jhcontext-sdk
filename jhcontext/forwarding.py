"""Forwarding policy enforcement for multi-task pipelines.

Framework-agnostic — no CrewAI imports. Agent runtimes (CrewAI, LangGraph,
etc.) call these utilities to enforce the protocol's forwarding constraints.
"""

from __future__ import annotations

import json
from typing import Any

from .models import Envelope, ForwardingPolicy


class ForwardingEnforcer:
    """Enforces forwarding policy constraints across a task pipeline.

    Tracks the **monotonic semantic boundary**: once any task sets
    ``semantic_forward``, subsequent tasks cannot downgrade to
    ``raw_forward``. Violations are overridden and logged.

    Usage::

        enforcer = ForwardingEnforcer()

        # Task 1: fetch step — raw_forward
        policy = enforcer.resolve(task1_envelope)  # RAW_FORWARD

        # Task 2: classification step — semantic_forward
        policy = enforcer.resolve(task2_envelope)  # SEMANTIC_FORWARD (boundary set)

        # Task 3: accidentally declares raw_forward
        policy = enforcer.resolve(task3_envelope)  # SEMANTIC_FORWARD (overridden)
    """

    def __init__(self) -> None:
        self._boundary_reached: bool = False

    @property
    def semantic_boundary_reached(self) -> bool:
        """Whether any task has set ``semantic_forward``."""
        return self._boundary_reached

    def resolve(self, task_envelope: Envelope) -> ForwardingPolicy:
        """Resolve the effective forwarding policy for a task's output.

        Reads ``task_envelope.compliance.forwarding_policy`` and applies
        monotonic enforcement. Returns the effective policy.
        """
        declared = task_envelope.compliance.forwarding_policy

        if self._boundary_reached and declared == ForwardingPolicy.RAW_FORWARD:
            print(
                "[PAC-AI] WARNING: task declared raw_forward after semantic "
                "boundary — overriding to semantic_forward (monotonic)"
            )
            declared = ForwardingPolicy.SEMANTIC_FORWARD

        if declared == ForwardingPolicy.SEMANTIC_FORWARD:
            self._boundary_reached = True

        return declared

    def filter_output(
        self,
        envelope: Envelope,
        policy: ForwardingPolicy | None = None,
    ) -> str:
        """Produce the filtered output string for the next task.

        For ``SEMANTIC_FORWARD``: returns only ``{"semantic_payload": [...]}``.
        For ``RAW_FORWARD``: returns the full envelope JSON.

        The agent runtime should replace the task's raw output with this
        string before the next task reads it.
        """
        if policy is None:
            policy = self.resolve(envelope)

        if policy == ForwardingPolicy.SEMANTIC_FORWARD:
            return json.dumps(
                {"semantic_payload": envelope.semantic_payload},
                indent=2,
                default=str,
            )
        return json.dumps(
            envelope.model_dump(mode="json", exclude_none=True),
            indent=2,
            default=str,
        )

    def reset(self) -> None:
        """Reset the boundary state (e.g., for a new pipeline run)."""
        self._boundary_reached = False
