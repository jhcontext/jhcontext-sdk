"""Tests for ForwardingEnforcer — uniform-policy enforcement."""

from __future__ import annotations

import json

import pytest

from jhcontext import (
    EnvelopeBuilder,
    ForwardingEnforcer,
    ForwardingPolicy,
    ForwardingPolicyViolation,
    RiskLevel,
)


def _envelope_with(policy: ForwardingPolicy):
    """Build a minimal signed envelope declaring *policy*."""
    return (
        EnvelopeBuilder()
        .set_producer("did:test:agent")
        .set_scope("forwarding-test")
        .set_risk_level(RiskLevel.HIGH if policy == ForwardingPolicy.SEMANTIC_FORWARD else RiskLevel.LOW)
        .set_forwarding_policy(policy)
        .sign("did:test:agent")
        .build()
    )


class TestConstruction:
    def test_requires_policy(self):
        with pytest.raises(TypeError):
            ForwardingEnforcer()  # type: ignore[call-arg]

    def test_rejects_non_policy(self):
        with pytest.raises(TypeError):
            ForwardingEnforcer("semantic_forward")  # type: ignore[arg-type]

    def test_records_policy(self):
        e = ForwardingEnforcer(ForwardingPolicy.SEMANTIC_FORWARD)
        assert e.policy == ForwardingPolicy.SEMANTIC_FORWARD


class TestResolveSemanticForwardPipeline:
    def test_uniform_semantic_passes(self):
        e = ForwardingEnforcer(ForwardingPolicy.SEMANTIC_FORWARD)
        env = _envelope_with(ForwardingPolicy.SEMANTIC_FORWARD)
        assert e.resolve(env) == ForwardingPolicy.SEMANTIC_FORWARD

    def test_raw_in_semantic_pipeline_raises(self):
        e = ForwardingEnforcer(ForwardingPolicy.SEMANTIC_FORWARD)
        env = _envelope_with(ForwardingPolicy.RAW_FORWARD)
        with pytest.raises(ForwardingPolicyViolation) as exc:
            e.resolve(env)
        assert "raw_forward" in str(exc.value)
        assert "semantic_forward" in str(exc.value)

    def test_no_implicit_relaxed_state(self):
        """The first task must already match — no warm-up phase."""
        e = ForwardingEnforcer(ForwardingPolicy.SEMANTIC_FORWARD)
        first_env = _envelope_with(ForwardingPolicy.RAW_FORWARD)
        with pytest.raises(ForwardingPolicyViolation):
            e.resolve(first_env)


class TestResolveRawForwardPipeline:
    def test_uniform_raw_passes(self):
        e = ForwardingEnforcer(ForwardingPolicy.RAW_FORWARD)
        env = _envelope_with(ForwardingPolicy.RAW_FORWARD)
        assert e.resolve(env) == ForwardingPolicy.RAW_FORWARD

    def test_semantic_in_raw_pipeline_raises(self):
        """Symmetry: a raw-pipeline task cannot 'upgrade' on its own."""
        e = ForwardingEnforcer(ForwardingPolicy.RAW_FORWARD)
        env = _envelope_with(ForwardingPolicy.SEMANTIC_FORWARD)
        with pytest.raises(ForwardingPolicyViolation):
            e.resolve(env)


class TestFilterOutput:
    def test_semantic_strips_to_payload_only(self):
        e = ForwardingEnforcer(ForwardingPolicy.SEMANTIC_FORWARD)
        env = _envelope_with(ForwardingPolicy.SEMANTIC_FORWARD)
        env.semantic_payload = [{"@model": "UserML", "k": "v"}]
        out = json.loads(e.filter_output(env))
        assert set(out.keys()) == {"semantic_payload"}
        assert out["semantic_payload"] == [{"@model": "UserML", "k": "v"}]

    def test_raw_keeps_full_envelope(self):
        e = ForwardingEnforcer(ForwardingPolicy.RAW_FORWARD)
        env = _envelope_with(ForwardingPolicy.RAW_FORWARD)
        out = json.loads(e.filter_output(env))
        assert "artifacts_registry" in out
        assert "proof" in out
        assert "semantic_payload" in out

    def test_explicit_policy_must_match_pipeline(self):
        e = ForwardingEnforcer(ForwardingPolicy.SEMANTIC_FORWARD)
        env = _envelope_with(ForwardingPolicy.SEMANTIC_FORWARD)
        with pytest.raises(ForwardingPolicyViolation):
            e.filter_output(env, ForwardingPolicy.RAW_FORWARD)


class TestPipelineComposition:
    """The supported way to mix modes: two enforcers, two pipelines."""

    def test_raw_then_semantic_compose_cleanly(self):
        raw = ForwardingEnforcer(ForwardingPolicy.RAW_FORWARD)
        sem = ForwardingEnforcer(ForwardingPolicy.SEMANTIC_FORWARD)

        raw_env = _envelope_with(ForwardingPolicy.RAW_FORWARD)
        sem_env = _envelope_with(ForwardingPolicy.SEMANTIC_FORWARD)

        # Each enforcer rejects the other's envelopes:
        with pytest.raises(ForwardingPolicyViolation):
            raw.resolve(sem_env)
        with pytest.raises(ForwardingPolicyViolation):
            sem.resolve(raw_env)

        # Within their own pipeline, both work:
        assert raw.resolve(raw_env) == ForwardingPolicy.RAW_FORWARD
        assert sem.resolve(sem_env) == ForwardingPolicy.SEMANTIC_FORWARD
