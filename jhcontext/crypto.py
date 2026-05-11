"""Cryptographic utilities for PAC-AI: hashing, signing, verification.

Ed25519 keys are persisted under ``$JHCONTEXT_KEYSTORE_DIR``
(default: ``~/.jhcontext/keys``) so that signing in one process and
verification in another (e.g. local API server) resolve the same public key.
The path is configurable for tests and CI runs.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from pathlib import Path
from typing import TYPE_CHECKING

from .canonicalize import algorithm as canonicalization_algorithm, canonicalize
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


def _keystore_dir() -> Path:
    """Resolve the keystore directory from env or fall back to ~/.jhcontext/keys."""
    env = os.environ.get("JHCONTEXT_KEYSTORE_DIR")
    if env:
        return Path(env)
    return Path.home() / ".jhcontext" / "keys"


def _safe_did_filename(did: str) -> str:
    """Replace unsafe path characters in a DID for use as a filename."""
    return did.replace("/", "_").replace(":", "_")


def _key_paths(signer_did: str) -> tuple[Path, Path]:
    """Return (private_key_path, public_key_path) for a signer DID."""
    base = _keystore_dir()
    name = _safe_did_filename(signer_did)
    return base / f"{name}.priv", base / f"{name}.pub"


def _load_or_create_private_key(signer_did: str):
    """Load an Ed25519 private key for the DID, generating + persisting it on first use."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization

    priv_path, pub_path = _key_paths(signer_did)

    if priv_path.exists():
        priv_bytes = priv_path.read_bytes()
        return Ed25519PrivateKey.from_private_bytes(priv_bytes)

    key = Ed25519PrivateKey.generate()
    priv_bytes = key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_bytes = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    priv_path.parent.mkdir(parents=True, exist_ok=True)
    priv_path.write_bytes(priv_bytes)
    priv_path.chmod(0o600)
    pub_path.write_bytes(pub_bytes)

    _KEYS[signer_did] = pub_bytes
    return key


def _load_public_key_bytes(signer_did: str) -> bytes | None:
    """Return the persisted public key bytes for a signer DID, or None."""
    if signer_did in _KEYS:
        return _KEYS[signer_did]
    _, pub_path = _key_paths(signer_did)
    if pub_path.exists():
        pub_bytes = pub_path.read_bytes()
        _KEYS[signer_did] = pub_bytes
        return pub_bytes
    return None


def sign_envelope(
    envelope: "Envelope",
    signer_did: str,
    mode: str | None = None,
) -> Proof:
    """Sign an envelope with Ed25519 (uses HMAC placeholder if cryptography not available).

    Parameters
    ----------
    envelope : Envelope
    signer_did : str
        DID under which the keypair is persisted in the keystore.
    mode : str | None
        Canonicalization mode override. When ``None`` falls back to the
        environment / default chosen by :func:`canonicalize`. The chosen
        algorithm is recorded in ``Proof.canonicalization`` so a verifier
        can recompute against the same form.
    """
    canonical = canonicalize(envelope.to_jsonld(include_proof=False), mode=mode)
    content_hash = compute_sha256(canonical.encode("utf-8"))

    try:
        private_key = _load_or_create_private_key(signer_did)
        signature_bytes = private_key.sign(content_hash.encode("utf-8"))
        signature = base64.urlsafe_b64encode(signature_bytes).decode("utf-8")
    except ImportError:
        signature = _hmac_sign(content_hash, signer_did)

    return Proof(
        canonicalization=canonicalization_algorithm(mode),
        content_hash=content_hash,
        signature=signature,
        signer=signer_did,
    )


def verify_envelope(envelope: "Envelope") -> bool:
    """Verify envelope integrity: recompute hash and check signature.

    The recomputation uses the algorithm recorded in
    ``envelope.proof.canonicalization`` so that envelopes signed with
    deterministic-JSON still verify on a peer that has pyld installed (and
    vice versa).
    """
    if not envelope.proof.content_hash or not envelope.proof.signature:
        return False

    proof_mode = envelope.proof.canonicalization
    canonical = canonicalize(
        envelope.to_jsonld(include_proof=False),
        mode=proof_mode if proof_mode else None,
    )
    recomputed = compute_sha256(canonical.encode("utf-8"))

    if recomputed != envelope.proof.content_hash:
        return False

    signer = envelope.proof.signer
    if not signer:
        return False

    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        pub_bytes = _load_public_key_bytes(signer)
        if pub_bytes is not None:
            public_key = Ed25519PublicKey.from_public_bytes(pub_bytes)
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
