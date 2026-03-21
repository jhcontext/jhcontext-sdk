"""REST API client for jhcontext server."""

from __future__ import annotations

import base64
from typing import Any

import httpx

from ..models import Envelope


class JHContextClient:
    """Client for communicating with a jhcontext server via REST API."""

    def __init__(
        self,
        base_url: str = "http://localhost:8400",
        api_key: str | None = None,
        tls_cert: str | None = None,
        tls_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        verify: bool | str = True
        cert: tuple[str, str] | None = None
        if tls_cert and tls_key:
            cert = (tls_cert, tls_key)

        self._client = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            verify=verify,
            cert=cert,
            timeout=timeout,
        )

    def submit_envelope(self, envelope: Envelope) -> str:
        resp = self._client.post("/envelopes", json={"envelope": envelope.to_jsonld()})
        resp.raise_for_status()
        return resp.json()["context_id"]

    def get_envelope(self, context_id: str) -> dict[str, Any]:
        resp = self._client.get(f"/envelopes/{context_id}")
        resp.raise_for_status()
        return resp.json()

    def list_envelopes(self, **filters: str) -> list[dict[str, Any]]:
        resp = self._client.get("/envelopes", params=filters)
        resp.raise_for_status()
        return resp.json()

    def upload_artifact(
        self,
        artifact_id: str,
        context_id: str,
        artifact_type: str,
        content: bytes,
        model: str | None = None,
        deterministic: bool = False,
    ) -> dict[str, Any]:
        resp = self._client.post(
            "/artifacts",
            json={
                "artifact_id": artifact_id,
                "context_id": context_id,
                "artifact_type": artifact_type,
                "content_base64": base64.b64encode(content).decode("utf-8"),
                "model": model,
                "deterministic": deterministic,
            },
        )
        resp.raise_for_status()
        return resp.json()

    def get_artifact(self, artifact_id: str) -> dict[str, Any]:
        resp = self._client.get(f"/artifacts/{artifact_id}")
        resp.raise_for_status()
        return resp.json()

    def log_decision(
        self,
        context_id: str,
        passed_artifact_id: str | None = None,
        outcome: dict[str, Any] | None = None,
        agent_id: str = "",
    ) -> str:
        resp = self._client.post(
            "/decisions",
            json={
                "context_id": context_id,
                "passed_artifact_id": passed_artifact_id,
                "outcome": outcome or {},
                "agent_id": agent_id,
            },
        )
        resp.raise_for_status()
        return resp.json()["decision_id"]

    def submit_prov_graph(self, context_id: str, graph_turtle: str) -> dict[str, Any]:
        resp = self._client.post(
            "/provenance",
            json={"context_id": context_id, "graph_turtle": graph_turtle},
        )
        resp.raise_for_status()
        return resp.json()

    def query_provenance(
        self, context_id: str, query_type: str, entity_id: str | None = None
    ) -> dict[str, Any]:
        resp = self._client.post(
            "/provenance/query",
            json={"context_id": context_id, "query_type": query_type, "entity_id": entity_id},
        )
        resp.raise_for_status()
        return resp.json()

    def export_compliance_package(self, context_id: str) -> bytes:
        resp = self._client.get(f"/compliance/package/{context_id}")
        resp.raise_for_status()
        return resp.content

    def health(self) -> dict[str, Any]:
        resp = self._client.get("/health")
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._client.close()
