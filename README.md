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
├── models.py          # Pydantic v2 data models (Envelope, Artifact, Decision, ForwardingPolicy, ...)
├── builder.py         # EnvelopeBuilder — fluent API for constructing envelopes
├── forwarding.py      # ForwardingEnforcer — monotonic policy enforcement + output filtering
├── persistence.py     # StepPersister — artifact + envelope + PROV persistence orchestration
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
    .set_risk_level(RiskLevel.HIGH)        # auto-sets forwarding_policy=semantic_forward
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
print(env.compliance.forwarding_policy)    # "semantic_forward"
```

### Forwarding policy

The `forwarding_policy` field in `ComplianceBlock` controls how the envelope's content
is forwarded between tasks in a multi-agent pipeline:

```python
from jhcontext import EnvelopeBuilder, RiskLevel, ForwardingPolicy

# HIGH risk → auto-sets semantic_forward
env = EnvelopeBuilder().set_risk_level(RiskLevel.HIGH).build()
assert env.compliance.forwarding_policy == ForwardingPolicy.SEMANTIC_FORWARD

# LOW risk → auto-sets raw_forward
env = EnvelopeBuilder().set_risk_level(RiskLevel.LOW).build()
assert env.compliance.forwarding_policy == ForwardingPolicy.RAW_FORWARD

# Explicit override (e.g., a fetch task in a HIGH-risk flow that needs raw_forward)
env = (
    EnvelopeBuilder()
    .set_risk_level(RiskLevel.HIGH)
    .set_forwarding_policy(ForwardingPolicy.RAW_FORWARD)  # override
    .build()
)
```

- **`semantic_forward`** — downstream consumers must read only `semantic_payload`.
  Raw tokens, embeddings, and artifact metadata are stripped before forwarding.
- **`raw_forward`** — downstream consumers receive the full envelope (all fields).

### ForwardingEnforcer

The SDK provides `ForwardingEnforcer` — a framework-agnostic class that enforces the
monotonic forwarding constraint across a task pipeline. No CrewAI imports required.

```python
from jhcontext import ForwardingEnforcer, ForwardingPolicy, Envelope

enforcer = ForwardingEnforcer()

# Task 1: fetch step — raw_forward (passes raw data to classifier)
policy = enforcer.resolve(task1_envelope)       # RAW_FORWARD
filtered = enforcer.filter_output(task1_envelope, policy)  # full envelope JSON

# Task 2: classification — semantic_forward (boundary is set)
policy = enforcer.resolve(task2_envelope)       # SEMANTIC_FORWARD
filtered = enforcer.filter_output(task2_envelope, policy)  # only {"semantic_payload": [...]}

# Task 3: accidentally declares raw_forward → overridden
policy = enforcer.resolve(task3_envelope)       # SEMANTIC_FORWARD (monotonic override)

print(enforcer.semantic_boundary_reached)       # True
```

The agent runtime (CrewAI, LangGraph, etc.) calls `enforcer.filter_output()` and replaces
the task's raw output with the result. The full envelope is still persisted to the backend
for audit — nothing is lost.

### StepPersister

Orchestrates artifact + envelope + PROV persistence for individual pipeline steps:

```python
from jhcontext import StepPersister, ArtifactType
from jhcontext.client.api_client import JHContextClient

persister = StepPersister(client=client, builder=builder, prov=prov, context_id="ctx-abc")

artifact_id = persister.persist(
    step_name="sensor",
    agent_id="did:hospital:sensor-agent",
    output="raw sensor data...",
    artifact_type=ArtifactType.TOKEN_SEQUENCE,
    started_at="2026-03-23T10:00:00Z",
    ended_at="2026-03-23T10:01:00Z",
)

metrics = persister.finalize_metrics(total_start=start_time)
```

Handles large artifact upload to S3 (>100 KB), envelope signing, PROV graph extension,
and step-level metrics collection.

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

### Crew delegation in PROV

Model multi-agent crews using standard W3C PROV vocabulary (`prov:actedOnBehalfOf`).
The PROV graph itself serves as the coordination layer — no external pipeline ID needed.

```python
from jhcontext import PROVGraph

prov = PROVGraph("ctx-pipeline")

# Register a crew (prov:Agent + prov:SoftwareAgent)
prov.add_crew("crew:clinical", "Clinical Pipeline Crew")

# Register agents and delegate to crew
prov.add_agent("did:hospital:sensor", "Sensor Agent", role="sensor")
prov.add_agent("did:hospital:decision", "Decision Agent", role="decision")
prov.acted_on_behalf_of("did:hospital:sensor", "crew:clinical")
prov.acted_on_behalf_of("did:hospital:decision", "crew:clinical")

# Oversight agent — explicitly outside the crew
prov.add_agent("did:hospital:dr-chen", "Dr. Chen", role="physician_oversight")

# Query all activities from the crew
activities = prov.get_crew_activities("crew:clinical")
agents = prov.get_crew_agents("crew:clinical")
crew = prov.get_agent_crew("did:hospital:sensor")  # "crew:clinical"

# Raw SPARQL works too
results = prov.query("""
    PREFIX prov: <http://www.w3.org/ns/prov#>
    PREFIX jh: <https://jhcontext.com/vocab#>
    SELECT ?activity ?label WHERE {
        ?agent prov:actedOnBehalfOf jh:crew-clinical .
        ?activity prov:wasAssociatedWith ?agent .
        ?activity rdfs:label ?label .
    }
""")
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
| **Forwarding Policy** | Per-envelope control: `semantic_forward` (only `semantic_payload` visible downstream) or `raw_forward` (full envelope). Monotonic — once semantic, cannot downgrade. |
| **ForwardingEnforcer** | Framework-agnostic monotonic policy enforcement. Resolves per-task policies and filters output for downstream consumers. |
| **StepPersister** | Orchestrates artifact + envelope + PROV persistence for individual pipeline steps. Handles S3 upload, signing, and metrics. |
| **PROVGraph** | W3C PROV provenance graph (entities, activities, agents, crew delegation, relations) |
| **Proof** | Cryptographic integrity: canonical hash + Ed25519/HMAC signature |
| **Audit** | Compliance checks: temporal oversight, negative proof, workflow isolation, PII detachment |
| **PII Detachment** | Tokenize PII before storage; separate vault enables GDPR erasure without breaking audit trails |
| **UserML** | Semantic payload format: observation → interpretation → situation layers |

## CrewAI Integration: Structured Output with `FlatEnvelope`

The full `Envelope` pydantic model has deeply nested types (`ComplianceBlock`, `Artifact`,
`Proof`, `PrivacyBlock`, etc.) that can exceed LLM structured output grammar limits —
particularly Anthropic's Haiku, which rejects schemas with too many nested object definitions.

`FlatEnvelope` solves this by providing a **scalar-only** pydantic model (no nested objects,
no `dict[str, Any]`) that any LLM can fill via structured output, then converts to a full
`Envelope` for protocol processing.

### Two options for CrewAI `output_pydantic`

| Option | Model | Schema complexity | LLM compatibility | Structured guarantee |
|--------|-------|-------------------|-------------------|---------------------|
| `output_pydantic=FlatEnvelope` | Flat, scalar-only fields | ~10 properties, 0 nested types | All (Haiku, Sonnet, GPT, Gemini) | Strict — LLM fills exact fields |
| *(no output_pydantic)* | Free-form JSON text | N/A | All | Loose — LLM writes JSON string, callback parses |

### Using `FlatEnvelope` (recommended)

```python
from crewai import Agent, Task
from jhcontext.flat_envelope import FlatEnvelope

@task
def sensor_task(self) -> Task:
    return Task(
        config=self.tasks_config["sensor_task"],
        output_pydantic=FlatEnvelope,  # Haiku-compatible structured output
    )
```

The task description should instruct the LLM to fill `FlatEnvelope` fields:

```yaml
sensor_task:
  description: >
    Collect clinical observations for patient {patient_id}.

    Output a FlatEnvelope with:
    - producer: "did:hospital:sensor-agent"
    - scope: "healthcare_treatment_recommendation"
    - semantic_payload_json: a JSON string containing the UserML payload
    - artifact_id: "art-sensor"
    - artifact_type: "token_sequence"
    - risk_level: "high"
    - human_oversight_required: true
    - forwarding_policy: "raw_forward"
```

### `FlatEnvelope` fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `producer` | str | `""` | Agent DID |
| `scope` | str | `""` | Workflow scope |
| `semantic_payload_json` | str | `"[]"` | Semantic payload as JSON string (parsed to `list[dict]` by `to_envelope()`) |
| `artifact_id` | str | auto-generated | Artifact identifier |
| `artifact_type` | str | `"semantic_extraction"` | One of: `token_sequence`, `embedding`, `semantic_extraction`, `tool_result` |
| `di_agent` | str | `""` | Decision influence agent name |
| `di_categories` | list[str] | `[]` | Decision influence categories |
| `risk_level` | str | `"medium"` | One of: `low`, `medium`, `high` |
| `human_oversight_required` | bool | `false` | Oversight flag |
| `forwarding_policy` | str | `"raw_forward"` | One of: `semantic_forward`, `raw_forward` |

### Converting to full `Envelope`

In your CrewAI task callback or flow code:

```python
from jhcontext.flat_envelope import FlatEnvelope

# CrewAI fills this via structured output:
flat: FlatEnvelope = output.pydantic

# Convert to full protocol Envelope:
envelope = flat.to_envelope()

# Now use envelope normally:
envelope.compliance.risk_level   # RiskLevel.HIGH
envelope.semantic_payload        # [{"subject": "P-001", ...}]
envelope.artifacts_registry      # [Artifact(artifact_id="art-sensor", ...)]
```

### Why not use `Envelope` directly?

The full `Envelope` schema generates ~50+ JSON Schema definitions with nested `$defs` for
`ComplianceBlock`, `Artifact`, `DecisionInfluence`, `PrivacyBlock`, `Proof`, etc. This
causes Anthropic's API to reject the request with:

> *"The compiled grammar is too large"* or *"Schema is too complex"*

`FlatEnvelope` produces a schema with **0 nested `$defs`** and **10 scalar properties** —
within any LLM provider's grammar limits.

## Protocol

Based on the **PAC-AI** (Protocol for Auditable Context in AI) specification. JSON-LD schema at `jhcontext-protocol/jhcontext-core.jsonld` (v0.3).

## License

Apache-2.0
