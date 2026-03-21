"""Cryptographic utilities for PAC-AI: hashing, signing, verification."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import TYPE_CHECKING

from .canonicalize import canonicalize
from .models import Proof

if TYPE_CHECKING:
    from .models import Envelope


def compute_sha256(data: bytes) -> str:
    """Compute SHA-256 hex digest."""
    return hashlib.sha256(data).hexdigest()


def compute_content_hash(obj: dict) -> str:
    """Canonicalize a dict and compute its SHA-256 hash."""
    canonical = canonicalize(obj)
    return compute_sha256(canonical.encode("utf-8"))


def sign_envelope(envelope: "Envelope", signer_did: str) -> Proof:
    """Sign an envelope with Ed25519 (uses HMAC placeholder if cryptography not available).

    In production, replace with real Ed25519 using the `cryptography` package.
    The signature covers the canonical JSON-LD form of the envelope.
    """
    canonical = canonicalize(envelope.to_jsonld(include_proof=False))
    content_hash = compute_sha256(canonical.encode("utf-8"))

    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        import base64

        private_key = Ed25519PrivateKey.generate()
        signature_bytes = private_key.sign(content_hash.encode("utf-8"))
        signature = base64.urlsafe_b64encode(signature_bytes).decode("utf-8")

        public_key_bytes = private_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        _KEYS[signer_did] = public_key_bytes
    except ImportError:
        signature = _hmac_sign(content_hash, signer_did)

    return Proof(
        canonicalization="URDNA2015",
        content_hash=content_hash,
        signature=signature,
        signer=signer_did,
    )


def verify_envelope(envelope: "Envelope") -> bool:
    """Verify envelope integrity: recompute hash and check signature."""
    if not envelope.proof.content_hash or not envelope.proof.signature:
        return False

    canonical = canonicalize(envelope.to_jsonld(include_proof=False))
    recomputed = compute_sha256(canonical.encode("utf-8"))

    if recomputed != envelope.proof.content_hash:
        return False

    signer = envelope.proof.signer
    if not signer:
        return False

    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        import base64

        if signer in _KEYS:
            public_key = Ed25519PublicKey.from_public_bytes(_KEYS[signer])
            sig_bytes = base64.urlsafe_b64decode(envelope.proof.signature)
            public_key.verify(sig_bytes, envelope.proof.content_hash.encode("utf-8"))
            return True
    except (ImportError, Exception):
        pass

    return _hmac_verify(
        envelope.proof.content_hash, envelope.proof.signature, signer
    )


# --- HMAC fallback (no cryptography package) ---

_KEYS: dict[str, bytes] = {}
_HMAC_SECRET = b"jhcontext-dev-only-do-not-use-in-production"


def _hmac_sign(content_hash: str, signer_did: str) -> str:
    msg = f"{signer_did}:{content_hash}".encode("utf-8")
    return hmac.new(_HMAC_SECRET, msg, hashlib.sha256).hexdigest()


def _hmac_verify(content_hash: str, signature: str, signer_did: str) -> bool:
    expected = _hmac_sign(content_hash, signer_did)
    return hmac.compare_digest(expected, signature)
