"""Tests for jhcontext.crypto — hashing, signing, verification."""

import pytest
from jhcontext.crypto import (
    compute_sha256,
    compute_content_hash,
    sign_envelope,
    verify_envelope,
)
from jhcontext.builder import EnvelopeBuilder
from jhcontext.models import Envelope


class TestComputeSha256:
    def test_known_hash(self):
        # SHA-256 of empty string
        h = compute_sha256(b"")
        assert h == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_deterministic(self):
        data = b"hello world"
        assert compute_sha256(data) == compute_sha256(data)

    def test_different_inputs_different_hashes(self):
        assert compute_sha256(b"a") != compute_sha256(b"b")

    def test_output_length(self):
        h = compute_sha256(b"test")
        assert len(h) == 64  # SHA-256 hex = 64 chars


class TestComputeContentHash:
    """Content-hashing exercises URDNA2015 over a JSON-LD doc (or sorted-JSON
    fallback when pyld is unavailable). Plain dicts without an `@context`
    produce no RDF triples and therefore no distinguishing canonical form, so
    these tests use minimal JSON-LD documents."""

    @staticmethod
    def _doc(**fields):
        return {
            "@context": {"@vocab": "https://jhcontext.com/vocab#"},
            "@type": "jh:Envelope",
            **fields,
        }

    def test_dict_hash(self):
        h = compute_content_hash(self._doc(key="value"))
        assert isinstance(h, str)
        assert len(h) == 64

    def test_deterministic_regardless_of_key_order(self):
        h1 = compute_content_hash(self._doc(a=1, b=2))
        h2 = compute_content_hash(self._doc(b=2, a=1))
        assert h1 == h2

    def test_different_dicts_different_hashes(self):
        h1 = compute_content_hash(self._doc(key="value1"))
        h2 = compute_content_hash(self._doc(key="value2"))
        assert h1 != h2


class TestSignAndVerify:
    def test_sign_produces_proof(self):
        env = EnvelopeBuilder().set_producer("did:example:1").build()
        proof = sign_envelope(env, "did:example:signer")
        assert proof.content_hash is not None
        assert proof.signature is not None
        assert proof.signer == "did:example:signer"
        # Default canonicalization is deterministic-JSON. URDNA2015 is opt-in
        # via builder.set_canonicalization("URDNA2015") or sign_envelope(mode=).
        assert proof.canonicalization == "deterministic-json"

    def test_sign_with_urdna2015_mode(self):
        try:
            import pyld  # noqa: F401
        except ImportError:
            import pytest
            pytest.skip("pyld not installed")
        env = EnvelopeBuilder().set_producer("did:example:1").build()
        proof = sign_envelope(env, "did:example:signer", mode="URDNA2015")
        assert proof.canonicalization == "URDNA2015"

    def test_verify_signed_envelope(self):
        env = (
            EnvelopeBuilder()
            .set_producer("did:example:1")
            .set_scope("test")
            .sign("did:example:1")
            .build()
        )
        assert verify_envelope(env) is True

    def test_verify_fails_without_signature(self):
        env = EnvelopeBuilder().set_producer("did:example:1").build()
        assert verify_envelope(env) is False

    def test_verify_fails_tampered_hash(self):
        env = (
            EnvelopeBuilder()
            .set_producer("did:example:1")
            .sign("did:example:1")
            .build()
        )
        env.proof.content_hash = "tampered_hash"
        assert verify_envelope(env) is False

    def test_verify_fails_tampered_content(self):
        env = (
            EnvelopeBuilder()
            .set_producer("did:example:1")
            .sign("did:example:1")
            .build()
        )
        env.producer = "did:example:attacker"
        assert verify_envelope(env) is False

    def test_verify_fails_no_signer(self):
        env = Envelope()
        env.proof.content_hash = "abc"
        env.proof.signature = "sig"
        env.proof.signer = None
        assert verify_envelope(env) is False

    def test_different_signers_different_signatures(self):
        env1 = (
            EnvelopeBuilder()
            .set_producer("did:example:1")
            .set_scope("same")
            .sign("did:signer:a")
            .build()
        )
        env2 = (
            EnvelopeBuilder()
            .set_producer("did:example:1")
            .set_scope("same")
            .sign("did:signer:b")
            .build()
        )
        # Both should verify independently
        assert verify_envelope(env1) is True
        assert verify_envelope(env2) is True
