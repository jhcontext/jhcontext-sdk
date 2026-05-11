"""Forwarding policy enforcement for multi-task pipelines.

A pipeline declares ONE forwarding policy at construction; every task in
the pipeline must agree. There is no relaxed/transitional state — mixing
modes is achieved by **composing pipelines**: a ``raw_forward`` pipeline's
output becomes the input of a separate ``semantic_forward`` pipeline.

Framework-agnostic — no CrewAI imports. Agent runtimes (CrewAI, LangGraph,
etc.) call these utilities to enforce the protocol's forwarding constraints.
"""

from __future__ import annotations

import json

from .models import Envelope, ForwardingPolicy


class ForwardingPolicyViolation(ValueError):
    """A task declared a forwarding policy that disagrees with the pipeline's."""


class ForwardingEnforcer:
    """Enforces a uniform forwarding policy across a task pipeline.

    The pipeline policy is fixed at construction. Each task envelope must
    declare the same policy or :meth:`resolve` raises
    :class:`ForwardingPolicyViolation`. A pipeline that needs both raw and
    semantic stages must be split into two pipelines, with the first
    pipeline's terminal artifact fed as the input to the second.

    Usage::

        # Stage 1: raw extraction pipeline
        raw = ForwardingEnforcer(ForwardingPolicy.RAW_FORWARD)
        for env in raw_pipeline_tasks:
            policy = raw.resolve(env)         # RAW_FORWARD
            forward_payload = raw.filter_output(env, policy)

        # Stage 2: semantic decision pipeline (consumes stage-1 output)
        sem = ForwardingEnforcer(ForwardingPolicy.SEMANTIC_FORWARD)
        for env in decision_pipeline_tasks:
            policy = sem.resolve(env)         # SEMANTIC_FORWARD
            forward_payload = sem.filter_output(env, policy)
    """

    def __init__(self, policy: ForwardingPolicy) -> None:
        if not isinstance(policy, ForwardingPolicy):
            raise TypeError(
                f"ForwardingEnforcer requires a ForwardingPolicy, got {type(policy).__name__}"
            )
        self._policy = policy

    @property
    def policy(self) -> ForwardingPolicy:
        """The pipeline's declared forwarding policy."""
        return self._policy

    def resolve(self, task_envelope: Envelope) -> ForwardingPolicy:
        """Return the pipeline policy after checking the task envelope agrees.

        Raises
        ------
        ForwardingPolicyViolation
            If the envelope declares a policy other than the pipeline's.
        """
        declared = task_envelope.compliance.forwarding_policy
        if declared != self._policy:
            raise ForwardingPolicyViolation(
                f"Task declared forwarding_policy={declared.value!r} but pipeline "
                f"is locked to {self._policy.value!r}. Mixed-mode requires "
                f"composing two pipelines (raw_forward -> semantic_forward)."
            )
        return self._policy

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
        elif policy != self._policy:
            raise ForwardingPolicyViolation(
                f"filter_output(policy={policy.value!r}) disagrees with pipeline "
                f"policy {self._policy.value!r}."
            )

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
