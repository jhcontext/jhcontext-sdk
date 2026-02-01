# jhcontext SDK (minimal draft)

**Package name reserved. Initial development in progress.**


This is a minimal, draft Python SDK for the **jhcontext** protocol.
It provides:
- Envelope construction & validation
- Deterministic canonicalization (JSON sort keys)
- SHA-256 hashing of the canonicalized envelope
- Simple mock DID sign/verify helpers for testing

**Status:** draft v0.0.1

## Quick usage

```python
from jhcontext import envelope

env = envelope.from_dict(YOUR_DICT)
env.validate()
can = env.canonical()
h = env.hash()
print("hash:", h)
```

This repo is for prototyping and testing. Replace the mock signing
functions with real cryptographic proofs (Linked Data Proofs) for production.


## Sample semantics

The SDK includes simple UserML helpers in `jhcontext.semantics` to construct semantic payloads.

Example:

```python
from jhcontext import from_dict
from jhcontext.semantics import sample_smart_office
import datetime
now = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
payload = sample_smart_office('user:alice', now)

# Build envelope
from jhcontext import ContextEnvelope
env_dict = {
  "@context": {"jh":"https://jhcontext.com/vocab#","prov":"http://www.w3.org/ns/prov#","@vocab":"https://jhcontext.com/vocab#"},
  "@type": "jh:Envelope",
  "context_id": "ctx-example-1",
  "schema_version": "jh:0.2",
  "producer": "did:example:agent-1",
  "created_at": now,
  "ttl": "PT30M",
  "status": "active",
  "performative": "inform",
  "semantic_payload": [ payload ],
  "proof": {"canonicalization":"URDNA2015","hash":"","signature":"","signer":""}
}
env = from_dict(env_dict)
env.validate()
print(env.canonical())
```
