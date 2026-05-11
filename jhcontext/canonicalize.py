"""Canonicalization for envelope hashing.

Two algorithms are supported:

- ``deterministic-json`` (default) — sorted-key compact JSON. Operates at
  the JSON syntax layer: equates only key reordering. Cost ~0.04 ms.
  Sufficient when the producer controls byte output (the common case for
  agents using this SDK end-to-end).
- ``URDNA2015`` (opt-in) — W3C RDF Dataset Canonicalization 2015, executed
  via pyld. Operates at the RDF graph layer: equates every JSON-LD spelling
  that produces the same triples (context aliasing, blank-node renaming,
  expanded-vs-compacted form). Cost ~3 ms. Earn its keep when an envelope
  is going to leave the producer's serializer (regulator portal hand-off,
  multi-vendor audit, federated agents using a different SDK).

Selection precedence: explicit ``mode=`` arg → env var
``JHCONTEXT_CANONICALIZATION`` → ``deterministic-json`` default. The chosen
algorithm is recorded in ``Proof.canonicalization`` so a reader always
knows which one to recompute against.
"""

from __future__ import annotations

import json
import os

URDNA2015 = "URDNA2015"
DETERMINISTIC_JSON = "deterministic-json"

try:
    from pyld import jsonld as _jsonld

    _PYLD_AVAILABLE = True
except ImportError:
    _jsonld = None
    _PYLD_AVAILABLE = False


def _resolve_mode(mode: str | None) -> str:
    """Pick the active mode: explicit arg → env var → deterministic-JSON default."""
    if mode is not None:
        if mode not in (URDNA2015, DETERMINISTIC_JSON):
            raise ValueError(
                f"Unknown canonicalization mode {mode!r}. "
                f"Expected {URDNA2015!r} or {DETERMINISTIC_JSON!r}."
            )
        return mode
    env = os.environ.get("JHCONTEXT_CANONICALIZATION")
    if env in (URDNA2015, DETERMINISTIC_JSON):
        return env
    return DETERMINISTIC_JSON


def algorithm(mode: str | None = None) -> str:
    """Return the canonicalization algorithm that would be used for *mode*.

    Falls back to deterministic-JSON when URDNA2015 was requested but pyld
    is unavailable.
    """
    chosen = _resolve_mode(mode)
    if chosen == URDNA2015 and not _PYLD_AVAILABLE:
        return DETERMINISTIC_JSON
    return chosen


def canonicalize(obj: dict, mode: str | None = None) -> str:
    """Return the canonical string form used for content hashing.

    Parameters
    ----------
    obj : dict
        The JSON-LD document to canonicalize.
    mode : {"URDNA2015", "deterministic-json"} | None, default None
        Override the algorithm for this call. When None, resolves via env
        and falls back to deterministic-JSON.
    """
    chosen = _resolve_mode(mode)
    if chosen == URDNA2015 and _PYLD_AVAILABLE:
        return _jsonld.normalize(
            obj,
            {"algorithm": "URDNA2015", "format": "application/n-quads"},
        )
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
