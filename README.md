# jhcontext SDK

**PAC-AI: Protocol for Auditable Context in AI** — Python SDK

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
├── pii.py             # PII detection, tokenization, detachment (GDPR Art. 5/17)
├── audit.py           # Compliance verification (temporal oversight, negative proof, isolation, PII)
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
        ├── sqlite.py   # SQLite backend (zero-config, ~/.jhcontext/)
        └── pii_vault.py # Separate PII vault (GDPR erasure support)
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

### PII Detachment (GDPR Art. 5/17)

Tokenize personal data in semantic payloads before storage. PII is stored in a separate vault linked by `context_id`, enabling independent erasure without breaking audit trails.

```python
from jhcontext import EnvelopeBuilder, verify_pii_detachment, verify_integrity
from jhcontext.pii import InMemoryPIIVault, reattach_pii

vault = InMemoryPIIVault()

# Build with PII detachment
env = (
    EnvelopeBuilder()
    .set_producer("did:example:triage-agent")
    .set_scope("healthcare")
    .set_semantic_payload([
        {"patient_name": "Alice Johnson", "patient_email": "alice@hospital.org",
         "diagnosis": "mild concussion", "recommendation": "24h observation"},
    ])
    .set_privacy(feature_suppression=["patient_name", "patient_email"])
    .enable_pii_detachment(vault=vault)
    .sign("did:example:triage-agent")
    .build()
)

# PII is tokenized
print(env.semantic_payload[0]["patient_name"])   # pii:tok-a1b2c3d4e5f6
print(env.semantic_payload[0]["diagnosis"])       # mild concussion (not PII)

# Audit: verify no PII leaks
assert verify_pii_detachment(env).passed
assert verify_integrity(env).passed

# GDPR Art. 17 erasure
vault.purge_by_context(env.context_id)

# Audit trail survives — hash covers detached payload
assert verify_integrity(env).passed

# Reattach (gracefully fails after purge — tokens remain)
resolved = reattach_pii(env.semantic_payload, vault)
```

The `feature_suppression` field in the privacy block specifies which fields are always tokenized. The `DefaultPIIDetector` also scans all string values for common PII patterns (emails, phones, IPs, SSNs).

For persistent storage, use `SQLitePIIVault` (from `jhcontext.server.storage.pii_vault`) — it stores PII in a separate database file that can be encrypted or deleted independently.

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
| **Audit** | Compliance checks: temporal oversight, negative proof, workflow isolation, PII detachment |
| **PII Detachment** | Tokenize PII before storage; separate vault enables GDPR erasure without breaking audit trails |
| **UserML** | Semantic payload format: observation → interpretation → situation layers |

## Protocol

Based on the **PAC-AI** (Protocol for Auditable Context in AI) specification. JSON-LD schema at `jhcontext-protocol/jhcontext-core.jsonld` (v0.3).

## License

Apache-2.0
