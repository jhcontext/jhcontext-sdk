"""Tests for PII detection, tokenization, and detachment."""

import pytest

from jhcontext.pii import (
    DefaultPIIDetector,
    InMemoryPIIVault,
    PIIMatch,
    detach_pii,
    is_pii_token,
    reattach_pii,
    tokenize_value,
)


# --- tokenize_value ---


def test_tokenize_deterministic():
    """Same input always produces the same token."""
    assert tokenize_value("alice@example.com") == tokenize_value("alice@example.com")


def test_tokenize_different_inputs():
    """Different inputs produce different tokens."""
    assert tokenize_value("alice@example.com") != tokenize_value("bob@example.com")


def test_tokenize_format():
    """Token has the expected pii:tok-<12hex> format."""
    token = tokenize_value("test")
    assert token.startswith("pii:tok-")
    assert len(token) == len("pii:tok-") + 12


def test_is_pii_token():
    assert is_pii_token("pii:tok-abc123def456")
    assert not is_pii_token("some-other-string")
    assert not is_pii_token("")
    assert not is_pii_token(42)


# --- DefaultPIIDetector.detect ---


class TestDefaultPIIDetector:
    def setup_method(self):
        self.detector = DefaultPIIDetector()

    def test_detect_email(self):
        matches = self.detector.detect("alice@example.com")
        assert any(t == "email" for t, _ in matches)

    def test_detect_email_in_text(self):
        matches = self.detector.detect("contact me at alice@example.com for info")
        assert any(t == "email" for t, _ in matches)

    def test_detect_phone(self):
        matches = self.detector.detect("+1-555-123-4567")
        assert any(t == "phone" for t, _ in matches)

    def test_detect_ip_address(self):
        matches = self.detector.detect("192.168.1.1")
        assert any(t == "ip_address" for t, _ in matches)

    def test_detect_ssn(self):
        matches = self.detector.detect("123-45-6789")
        assert any(t == "ssn" for t, _ in matches)

    def test_no_false_positive_context_id(self):
        """context_id and UUID strings should not be flagged."""
        matches = self.detector.detect("ctx-550e8400-e29b-41d4-a716-446655440000")
        assert len(matches) == 0

    def test_no_false_positive_hash(self):
        matches = self.detector.detect("a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4")
        assert len(matches) == 0

    def test_no_false_positive_pii_token(self):
        """Already-tokenized values should not be re-detected."""
        matches = self.detector.detect("pii:tok-a1b2c3d4e5f6")
        assert len(matches) == 0


# --- DefaultPIIDetector.scan_payload ---


class TestScanPayload:
    def test_scan_finds_email_in_payload(self):
        detector = DefaultPIIDetector()
        payload = [{"subject": "alice@example.com", "observation": "location", "value": "home"}]
        matches = detector.scan_payload(payload)
        assert len(matches) == 1
        assert matches[0].detection_type == "email"
        assert matches[0].field_path == "[0].subject"

    def test_scan_with_feature_suppression(self):
        detector = DefaultPIIDetector(suppressed_fields=["patient_name"])
        payload = [{"patient_name": "John Doe", "diagnosis": "healthy"}]
        matches = detector.scan_payload(payload)
        assert len(matches) == 1
        assert matches[0].detection_type == "suppressed_field"
        assert matches[0].original_value == "John Doe"

    def test_scan_suppressed_field_overrides_regex(self):
        """Suppressed fields are flagged even without regex match."""
        detector = DefaultPIIDetector(suppressed_fields=["nickname"])
        payload = [{"nickname": "Jazz"}]
        matches = detector.scan_payload(payload)
        assert len(matches) == 1
        assert matches[0].detection_type == "suppressed_field"

    def test_scan_preserves_non_pii(self):
        detector = DefaultPIIDetector()
        payload = [{"observation": "location", "value": "home"}]
        matches = detector.scan_payload(payload)
        assert len(matches) == 0

    def test_scan_multiple_items(self):
        detector = DefaultPIIDetector()
        payload = [
            {"subject": "alice@example.com"},
            {"subject": "bob@example.com"},
        ]
        matches = detector.scan_payload(payload)
        assert len(matches) == 2

    def test_scan_nested_dict(self):
        detector = DefaultPIIDetector()
        payload = [{"user": {"email": "alice@example.com"}}]
        matches = detector.scan_payload(payload)
        assert len(matches) == 1
        assert matches[0].field_path == "[0].user.email"

    def test_scan_skips_existing_tokens(self):
        detector = DefaultPIIDetector(suppressed_fields=["subject"])
        payload = [{"subject": "pii:tok-a1b2c3d4e5f6"}]
        matches = detector.scan_payload(payload)
        assert len(matches) == 0


# --- detach_pii ---


class TestDetachPII:
    def test_detach_replaces_pii(self):
        vault = InMemoryPIIVault()
        detector = DefaultPIIDetector()
        payload = [{"subject": "alice@example.com", "value": "home"}]

        result = detach_pii(payload, "ctx-1", detector, vault)

        assert is_pii_token(result[0]["subject"])
        assert result[0]["value"] == "home"

    def test_detach_does_not_modify_original(self):
        vault = InMemoryPIIVault()
        detector = DefaultPIIDetector()
        payload = [{"subject": "alice@example.com"}]

        detach_pii(payload, "ctx-1", detector, vault)

        assert payload[0]["subject"] == "alice@example.com"

    def test_detach_stores_in_vault(self):
        vault = InMemoryPIIVault()
        detector = DefaultPIIDetector()
        payload = [{"subject": "alice@example.com"}]

        result = detach_pii(payload, "ctx-1", detector, vault)
        token = result[0]["subject"]

        assert vault.retrieve(token) == "alice@example.com"

    def test_detach_with_feature_suppression(self):
        vault = InMemoryPIIVault()
        detector = DefaultPIIDetector(suppressed_fields=["patient_name"])
        payload = [{"patient_name": "John Doe", "condition": "healthy"}]

        result = detach_pii(payload, "ctx-1", detector, vault)

        assert is_pii_token(result[0]["patient_name"])
        assert result[0]["condition"] == "healthy"

    def test_detach_preserves_non_pii(self):
        vault = InMemoryPIIVault()
        detector = DefaultPIIDetector()
        payload = [{"observation": "location", "value": "home"}]

        result = detach_pii(payload, "ctx-1", detector, vault)

        assert result[0]["observation"] == "location"
        assert result[0]["value"] == "home"


# --- reattach_pii ---


class TestReattachPII:
    def test_roundtrip(self):
        vault = InMemoryPIIVault()
        detector = DefaultPIIDetector()
        payload = [{"subject": "alice@example.com", "value": "home"}]

        detached = detach_pii(payload, "ctx-1", detector, vault)
        reattached = reattach_pii(detached, vault)

        assert reattached[0]["subject"] == "alice@example.com"
        assert reattached[0]["value"] == "home"

    def test_reattach_after_purge(self):
        """After purging, tokens remain as-is (unresolvable)."""
        vault = InMemoryPIIVault()
        detector = DefaultPIIDetector()
        payload = [{"subject": "alice@example.com"}]

        detached = detach_pii(payload, "ctx-1", detector, vault)
        token = detached[0]["subject"]

        vault.purge_by_context("ctx-1")
        reattached = reattach_pii(detached, vault)

        # Token stays since it can't be resolved
        assert reattached[0]["subject"] == token
        assert is_pii_token(reattached[0]["subject"])

    def test_reattach_does_not_modify_original(self):
        vault = InMemoryPIIVault()
        detector = DefaultPIIDetector()
        payload = [{"subject": "alice@example.com"}]

        detached = detach_pii(payload, "ctx-1", detector, vault)
        detached_copy = detached[0]["subject"]

        reattach_pii(detached, vault)

        assert detached[0]["subject"] == detached_copy
