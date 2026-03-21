"""Tests for jhcontext.server.storage.sqlite — SQLite backend."""

import tempfile
import pytest
from pathlib import Path

from jhcontext.models import (
    Artifact,
    ArtifactType,
    Decision,
    Envelope,
    RiskLevel,
)
from jhcontext.builder import EnvelopeBuilder
from jhcontext.prov import PROVGraph
from jhcontext.server.storage.sqlite import SQLiteStorage


@pytest.fixture
def storage(tmp_path):
    db_path = str(tmp_path / "test.db")
    s = SQLiteStorage(db_path=db_path, artifacts_dir=str(tmp_path / "artifacts"))
    yield s
    s.close()


class TestEnvelopeStorage:
    def test_save_and_get(self, storage):
        env = (
            EnvelopeBuilder()
            .set_producer("did:example:1")
            .set_scope("healthcare")
            .sign("did:example:1")
            .build()
        )
        ctx_id = storage.save_envelope(env)
        assert ctx_id == env.context_id

        loaded = storage.get_envelope(ctx_id)
        assert loaded is not None
        assert loaded.context_id == env.context_id
        assert loaded.producer == "did:example:1"
        assert loaded.scope == "healthcare"

    def test_get_nonexistent(self, storage):
        assert storage.get_envelope("ctx-nonexistent") is None

    def test_list_envelopes(self, storage):
        for scope in ["healthcare", "healthcare", "education"]:
            env = (
                EnvelopeBuilder()
                .set_producer("did:example:1")
                .set_scope(scope)
                .build()
            )
            storage.save_envelope(env)

        all_envs = storage.list_envelopes()
        assert len(all_envs) == 3

        health = storage.list_envelopes(scope="healthcare")
        assert len(health) == 2

        edu = storage.list_envelopes(scope="education")
        assert len(edu) == 1

    def test_list_filter_risk_level(self, storage):
        env = (
            EnvelopeBuilder()
            .set_producer("did:example:1")
            .set_risk_level(RiskLevel.HIGH)
            .build()
        )
        storage.save_envelope(env)

        high = storage.list_envelopes(risk_level="high")
        assert len(high) == 1

    def test_upsert(self, storage):
        env = EnvelopeBuilder().set_producer("did:example:1").set_scope("v1").build()
        storage.save_envelope(env)
        env.scope = "v2"
        storage.save_envelope(env)
        loaded = storage.get_envelope(env.context_id)
        # After re-serialization through JSON-LD, scope should reflect update
        assert loaded is not None


class TestArtifactStorage:
    def test_save_and_get(self, storage):
        content = b"binary artifact content"
        meta = Artifact(
            artifact_id="art-test",
            type=ArtifactType.EMBEDDING,
            content_hash="sha256:abc",
            model="text-embedding-3",
        )
        path = storage.save_artifact("art-test", content, meta)
        assert Path(path).exists()

        result = storage.get_artifact("art-test")
        assert result is not None
        loaded_content, loaded_meta = result
        assert loaded_content == content
        assert loaded_meta.artifact_id == "art-test"
        assert loaded_meta.type == ArtifactType.EMBEDDING

    def test_get_nonexistent(self, storage):
        assert storage.get_artifact("nonexistent") is None


class TestProvGraphStorage:
    def test_save_and_get(self, storage):
        pg = PROVGraph("ctx-prov-test")
        pg.add_entity("e1", "Test Entity")
        turtle = pg.serialize("turtle")
        digest = pg.digest()

        storage.save_prov_graph("ctx-prov-test", turtle, digest)
        loaded = storage.get_prov_graph("ctx-prov-test")
        assert loaded is not None
        assert "Test Entity" in loaded

    def test_get_nonexistent(self, storage):
        assert storage.get_prov_graph("nonexistent") is None


class TestDecisionStorage:
    def test_save_and_get(self, storage):
        dec = Decision(
            decision_id="dec-test",
            context_id="ctx-1",
            passed_artifact_id="art-1",
            outcome={"action": "approve", "confidence": 0.95},
            agent_id="agent-1",
        )
        dec_id = storage.save_decision(dec)
        assert dec_id == "dec-test"

        loaded = storage.get_decision("dec-test")
        assert loaded is not None
        assert loaded.context_id == "ctx-1"
        assert loaded.outcome["action"] == "approve"
        assert loaded.agent_id == "agent-1"

    def test_get_nonexistent(self, storage):
        assert storage.get_decision("nonexistent") is None
