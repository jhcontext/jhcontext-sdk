"""PII detection, tokenization, and detachment for PAC-AI envelopes.

Implements the PII Detachment pattern described in the PAC-AI protocol:
- Detect PII in semantic payloads (regex-based + feature_suppression fields)
- Replace PII with opaque tokens (pii:tok-<sha256[:12]>)
- Store originals in a separate PII vault linked by context_id
- Support independent erasure (GDPR Art. 17) without breaking audit trails
"""

from __future__ import annotations

import copy
import hashlib
import re
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class PIIMatch:
    """A detected PII occurrence in a semantic payload."""

    field_path: str
    original_value: str
    detection_type: str  # "email", "phone", "ip_address", "ssn", "suppressed_field"


@runtime_checkable
class PIIDetector(Protocol):
    """Interface for PII detection strategies."""

    def detect(self, value: str) -> list[tuple[str, str]]:
        """Return list of (detection_type, matched_substring) for a single value."""
        ...

    def scan_payload(self, payload: list[dict[str, Any]]) -> list[PIIMatch]:
        """Scan an entire semantic payload and return all PII matches."""
        ...


@runtime_checkable
class PIIVault(Protocol):
    """Interface for PII token storage."""

    def store(self, token_id: str, context_id: str, original_value: str, field_path: str) -> None:
        ...

    def retrieve(self, token_id: str) -> str | None:
        ...

    def retrieve_by_context(self, context_id: str) -> list[dict[str, str]]:
        ...

    def purge_by_context(self, context_id: str) -> int:
        ...

    def purge_expired(self, before_iso: str) -> int:
        ...


# --- Token generation ---

_PII_TOKEN_PREFIX = "pii:tok-"


def tokenize_value(value: str) -> str:
    """Generate a deterministic PII token: pii:tok-<sha256[:12]>."""
    h = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"{_PII_TOKEN_PREFIX}{h}"


def is_pii_token(value: str) -> bool:
    """Check if a string is a PII token."""
    return isinstance(value, str) and value.startswith(_PII_TOKEN_PREFIX)


# --- Default PII detector ---

_PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
    "phone": re.compile(r"(?<![a-zA-Z0-9\-])\+?(?:\d[\s\-()]*){7,15}(?![a-zA-Z0-9\-])"),
    "ip_address": re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
}


class DefaultPIIDetector:
    """Regex-based PII detector with feature_suppression enforcement.

    Fields listed in ``suppressed_fields`` are always flagged as PII regardless
    of their content. All string values are additionally scanned against common
    PII patterns (email, phone, IP address, SSN).
    """

    def __init__(self, suppressed_fields: list[str] | None = None) -> None:
        self.suppressed_fields = suppressed_fields or []

    def detect(self, value: str) -> list[tuple[str, str]]:
        """Scan a single string value for PII patterns."""
        matches: list[tuple[str, str]] = []
        for ptype, pattern in _PII_PATTERNS.items():
            for m in pattern.finditer(value):
                matches.append((ptype, m.group()))
        return matches

    def scan_payload(self, payload: list[dict[str, Any]]) -> list[PIIMatch]:
        """Walk the payload and return all PII matches."""
        results: list[PIIMatch] = []

        for idx, item in enumerate(payload):
            if not isinstance(item, dict):
                continue
            self._scan_dict(item, f"[{idx}]", results)

        return results

    def _scan_dict(self, d: dict[str, Any], prefix: str, results: list[PIIMatch]) -> None:
        for key, value in d.items():
            path = f"{prefix}.{key}"

            if key in self.suppressed_fields:
                if isinstance(value, str) and not is_pii_token(value):
                    results.append(PIIMatch(path, value, "suppressed_field"))
                continue

            if isinstance(value, str) and not is_pii_token(value):
                detections = self.detect(value)
                if detections:
                    # Use the full string value as the PII to replace
                    results.append(PIIMatch(path, value, detections[0][0]))
            elif isinstance(value, dict):
                self._scan_dict(value, path, results)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        self._scan_dict(item, f"{path}[{i}]", results)
                    elif isinstance(item, str) and not is_pii_token(item):
                        detections = self.detect(item)
                        if detections:
                            results.append(PIIMatch(f"{path}[{i}]", item, detections[0][0]))


# --- In-memory vault (for testing) ---


class InMemoryPIIVault:
    """Simple in-memory PII vault for testing and single-process use."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, str]] = {}

    def store(self, token_id: str, context_id: str, original_value: str, field_path: str) -> None:
        self._store[token_id] = {
            "context_id": context_id,
            "original_value": original_value,
            "field_path": field_path,
        }

    def retrieve(self, token_id: str) -> str | None:
        entry = self._store.get(token_id)
        return entry["original_value"] if entry else None

    def retrieve_by_context(self, context_id: str) -> list[dict[str, str]]:
        return [
            {"token_id": tid, **entry}
            for tid, entry in self._store.items()
            if entry["context_id"] == context_id
        ]

    def purge_by_context(self, context_id: str) -> int:
        to_delete = [tid for tid, e in self._store.items() if e["context_id"] == context_id]
        for tid in to_delete:
            del self._store[tid]
        return len(to_delete)

    def purge_expired(self, before_iso: str) -> int:
        return 0  # In-memory vault does not track timestamps


# --- Core detach / reattach functions ---


def detach_pii(
    payload: list[dict[str, Any]],
    context_id: str,
    detector: PIIDetector,
    vault: PIIVault,
) -> list[dict[str, Any]]:
    """Replace PII in payload with opaque tokens, store originals in vault.

    Returns a deep copy of the payload with PII replaced. The original is not modified.
    """
    result = copy.deepcopy(payload)
    matches = detector.scan_payload(result)

    for match in matches:
        token = tokenize_value(match.original_value)
        vault.store(token, context_id, match.original_value, match.field_path)
        _set_by_path(result, match.field_path, token)

    return result


def reattach_pii(
    payload: list[dict[str, Any]],
    vault: PIIVault,
) -> list[dict[str, Any]]:
    """Resolve PII tokens back to original values using the vault.

    Returns a deep copy. Tokens that cannot be resolved (e.g., after purge)
    remain as-is in the output.
    """
    result = copy.deepcopy(payload)
    _walk_and_resolve(result, vault)
    return result


# --- Path utilities ---

_PATH_RE = re.compile(r"\[(\d+)\]|\.(\w+)")


def _set_by_path(obj: Any, path: str, value: str) -> None:
    """Set a value in a nested structure using a dotted path like '[0].subject'."""
    parts = _PATH_RE.findall(path)
    current = obj
    for i, (idx_str, key) in enumerate(parts[:-1]):
        if idx_str:
            current = current[int(idx_str)]
        else:
            current = current[key]

    last_idx, last_key = parts[-1]
    if last_idx:
        current[int(last_idx)] = value
    else:
        current[last_key] = value


def _walk_and_resolve(obj: Any, vault: PIIVault) -> None:
    """Recursively walk a structure, resolving PII tokens via the vault."""
    if isinstance(obj, dict):
        for key in list(obj.keys()):
            val = obj[key]
            if isinstance(val, str) and is_pii_token(val):
                resolved = vault.retrieve(val)
                if resolved is not None:
                    obj[key] = resolved
            elif isinstance(val, (dict, list)):
                _walk_and_resolve(val, vault)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, str) and is_pii_token(item):
                resolved = vault.retrieve(item)
                if resolved is not None:
                    obj[i] = resolved
            elif isinstance(item, (dict, list)):
                _walk_and_resolve(item, vault)
