import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict
from .canonicalize import canonicalize
from .validate import validate_envelope
from .utils import compute_sha256_hex, mock_sign, mock_verify

@dataclass
class ContextEnvelope:
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return self.raw

    def canonical(self) -> str:
        # Use deterministic JSON canonicalization (sorted keys)
        return canonicalize(self.raw)

    def hash(self) -> str:
        can = self.canonical().encode('utf-8')
        return compute_sha256_hex(can)

    def validate(self) -> None:
        validate_envelope(self.raw)

    def sign(self, signer_did: str) -> Dict[str,str]:
        # Mock linked-data proof: in production replace with real LD-JSON-LD proof
        h = self.hash()
        sig = mock_sign(h, signer_did)
        return {"hash": h, "signature": sig, "signer": signer_did}

    def verify_signature(self, signature: str, signer_did: str) -> bool:
        h = self.hash()
        return mock_verify(h, signature, signer_did)

def from_dict(d: Dict) -> ContextEnvelope:
    return ContextEnvelope(raw=d)
