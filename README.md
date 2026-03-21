# jhcontext SDK

**PAC-AI: Protocol for Auditable Context in AI** — Python SDK v0.2.0

A Python toolkit for building, signing, auditing, and serving AI context envelopes compliant with the PAC-AI protocol. Designed for EU AI Act compliance scenarios including temporal oversight (Art. 14) and negative proof (Art. 13).

## Install

```bash
# Core: models, builder, PROV, audit, crypto
pip install jhcontext

# With server (FastAPI + MCP + SQLite)
pip install "jhcontext[server]"

# With CrewAI integration
pip install "jhcontext[crewai]"

# Everything
pip install "jhcontext[all]"

# Development (adds pytest)
pip install "jhcontext[all,dev]"
```

## Architecture

```
jhcontext/
├── models.py          # Pydantic v2 data models (Envelope, Artifact, Decision, ...)
├── builder.py         # EnvelopeBuilder — fluent API for constructing envelopes
├── prov.py            # PROVGraph — W3C PROV graph builder (rdflib)
├── audit.py           # Compliance verification (temporal oversight, negative proof, isolation)
├── crypto.py          # SHA-256 hashing, Ed25519 signing (HMAC fallback)
├── canonicalize.py    # Deterministic JSON serialization
├── semantics.py       # UserML semantic payload helpers
├── cli.py             # CLI: jhcontext serve | mcp | version
├── client/
│   └── api_client.py  # REST client (httpx)
└── server/
    ├── app.py          # FastAPI app factory
    ├── mcp_server.py   # MCP server (stdio transport)
    ├── routes/         # REST API routes (envelopes, artifacts, decisions, provenance, compliance)
    └── storage/
        └── sqlite.py   # SQLite backend (zero-config, ~/.jhcontext/)
```

## Quick Start

### Build and sign an envelope

```python
from jhcontext import EnvelopeBuilder, RiskLevel, ArtifactType, observation, userml_payload

# Build semantic payload
payload = userml_payload(
    observations=[observation("user:alice", "temperature", 22.3)],
)

# Build envelope
env = (
    EnvelopeBuilder()
    .set_producer("did:example:agent-1")
    .set_scope("healthcare")
    .set_risk_level(RiskLevel.HIGH)
    .set_human_oversight(True)
    .set_semantic_payload([payload])
    .add_artifact(
        artifact_id="art-vitals",
        artifact_type=ArtifactType.TOKEN_SEQUENCE,
        content_hash="sha256:abc123...",
    )
    .sign("did:example:agent-1")
    .build()
)

print(env.context_id)
print(env.proof.content_hash)
```

### Build a W3C PROV graph

```python
from jhcontext import PROVGraph

prov = (
    PROVGraph("ctx-health-001")
    .add_entity("vitals", "Patient Vitals", artifact_type="token_sequence")
    .add_entity("recommendation", "AI Recommendation")
    .add_activity("ai-analysis", "AI Analysis",
                  started_at="2026-01-01T10:00:00Z",
                  ended_at="2026-01-01T10:01:00Z")
    .add_agent("agent-sensor", "Sensor Agent", role="data_collector")
    .used("ai-analysis", "vitals")
    .was_generated_by("recommendation", "ai-analysis")
    .was_associated_with("ai-analysis", "agent-sensor")
    .was_derived_from("recommendation", "vitals")
)

# Serialize
print(prov.serialize("turtle"))

# Query
chain = prov.get_causal_chain("recommendation")
used = prov.get_used_entities("ai-analysis")
sequence = prov.get_temporal_sequence()
```

### Run compliance audits

```python
from jhcontext import (
    verify_temporal_oversight,
    verify_negative_proof,
    verify_workflow_isolation,
    verify_integrity,
    generate_audit_report,
)

# Art. 14 — Temporal oversight (human reviewed AFTER AI, >= 5 min)
result = verify_temporal_oversight(
    prov,
    ai_activity_id="ai-analysis",
    human_activities=["doctor-review"],
    min_review_seconds=300.0,
)

# Art. 13 — Negative proof (excluded data types not in decision chain)
result = verify_negative_proof(
    prov,
    decision_entity_id="final-grade",
    excluded_artifact_types=["biometric", "social_media"],
)

# Workflow isolation (two PROV graphs share zero artifacts)
result = verify_workflow_isolation(prov_a, prov_b)

# Envelope integrity (hash + signature)
result = verify_integrity(env)

# Generate full audit report
report = generate_audit_report(env, prov, [result1, result2, result3])
print(report.to_dict())
```

### Start the server

```bash
# REST API on localhost:8400
jhcontext serve

# MCP server (stdio transport)
jhcontext mcp
```

### Use the REST client

```python
from jhcontext.client.api_client import JHContextClient

client = JHContextClient(base_url="http://localhost:8400")

# Submit envelope
ctx_id = client.submit_envelope(env)

# Retrieve
data = client.get_envelope(ctx_id)

# List with filters
envelopes = client.list_envelopes(scope="healthcare")

# Health check
print(client.health())

client.close()
```

## Testing

```bash
pip install -e ".[all,dev]"
pytest tests/ --ignore=tests/test_example.py -v
```

## Key Concepts

| Concept | Description |
|---------|-------------|
| **Envelope** | Immutable context unit: semantic payload + artifacts + provenance + proof |
| **Artifact** | Registered data object (embedding, token sequence, tool result) with content hash |
| **PROVGraph** | W3C PROV provenance graph (entities, activities, agents, relations) |
| **Proof** | Cryptographic integrity: canonical hash + Ed25519/HMAC signature |
| **Audit** | Compliance checks: temporal oversight, negative proof, workflow isolation |
| **UserML** | Semantic payload format: observation → interpretation → situation layers |

## Protocol

Based on the **PAC-AI** (Protocol for Auditable Context in AI) specification. JSON-LD schema at `jhcontext-protocol/jhcontext-core.jsonld` (v0.3).

## License

Apache-2.0
