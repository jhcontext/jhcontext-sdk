"""Tests for jhcontext.server — FastAPI app and routes."""

import tempfile
import pytest
from fastapi.testclient import TestClient

from jhcontext.builder import EnvelopeBuilder
from jhcontext.models import RiskLevel
from jhcontext.server.app import create_app


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app(db_path=db_path)
    with TestClient(app) as c:
        yield c


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.2.0"


class TestEnvelopeRoutes:
    def _make_envelope_dict(self, **kwargs):
        env = (
            EnvelopeBuilder()
            .set_producer(kwargs.get("producer", "did:example:1"))
            .set_scope(kwargs.get("scope", "test"))
            .sign(kwargs.get("signer", "did:example:1"))
            .build()
        )
        return env.to_jsonld()

    def test_submit_and_get(self, client):
        env_dict = self._make_envelope_dict()
        # Submit
        resp = client.post("/envelopes", json={"envelope": env_dict})
        assert resp.status_code == 201
        data = resp.json()
        ctx_id = data["context_id"]
        assert ctx_id is not None

        # Get
        resp = client.get(f"/envelopes/{ctx_id}")
        assert resp.status_code == 200
        loaded = resp.json()
        assert loaded["context_id"] == ctx_id
        assert loaded["@type"] == "jh:Envelope"

    def test_get_nonexistent(self, client):
        resp = client.get("/envelopes/ctx-nonexistent")
        assert resp.status_code == 404

    def test_list_envelopes(self, client):
        for scope in ["healthcare", "education"]:
            env_dict = self._make_envelope_dict(scope=scope)
            client.post("/envelopes", json={"envelope": env_dict})

        resp = client.get("/envelopes")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_list_filter_by_scope(self, client):
        for scope in ["healthcare", "healthcare", "education"]:
            env_dict = self._make_envelope_dict(scope=scope)
            client.post("/envelopes", json={"envelope": env_dict})

        resp = client.get("/envelopes?scope=healthcare")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
