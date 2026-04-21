"""UserML semantic-statement helpers for the jhcontext SDK (v0.4).

Each function returns one atomic **semantic statement** — a single entry of an
envelope's ``semantic_payload`` list. Statements are expressed in **UserML**, a
markup language over RDF whose tuples reference external ontologies (SNOMED,
FHIR, QTI, custom RDF), enabling SPARQL indexing and downstream reasoning.

Per-statement shape (Heckmann-faithful, protocol v0.4):

- ``@model``     — discriminator, ``"UserML"``
- ``layer``      — type-tag, one of ``observation`` | ``interpretation`` |
                   ``situation`` | ``application``
- ``mainpart``   — the core claim ``{subject, auxiliary, predicate, range}``.
                   Heckmann's trio is ``auxiliary/predicate/range``; PAC-AI adds
                   an explicit ``subject`` slot for multi-subject context.
- ``situation``  — *(optional)* temporal/spatial box: ``start``, ``end``,
                   ``durability``, ``location``.
- ``explanation``— *(optional)* epistemic metadata: ``confidence``, ``creator``,
                   ``source``, ``method``, ``evidence``.

Heckmann's ``privacy`` and ``administration`` boxes live at envelope level
(governance block and proof block, respectively).
"""

from typing import Any


def _statement(layer: str, subject: str, auxiliary: str, predicate: str,
               value: Any, situation: dict | None = None,
               explanation: dict | None = None) -> dict:
    stmt: dict[str, Any] = {
        "@model": "UserML",
        "layer": layer,
        "mainpart": {
            "subject": subject,
            "auxiliary": auxiliary,
            "predicate": predicate,
            "range": value,
        },
    }
    if situation:
        stmt["situation"] = situation
    if explanation:
        stmt["explanation"] = explanation
    return stmt


def observation(subject: str, predicate: str, value: Any,
                source: str | None = None) -> dict:
    """Build an observation-layer semantic statement.

    Auxiliary defaults to ``hasProperty`` — the neutral modal operator for
    direct sensor/metadata facts. Callers with richer modality (e.g.,
    ``hasLocation``, ``hasTimestamp``) can construct the statement directly.
    """
    explanation = {"source": source} if source else None
    return _statement("observation", subject, "hasProperty", predicate, value,
                      explanation=explanation)


def interpretation(subject: str, predicate: str, value: Any,
                   confidence: float = 0.9, creator: str | None = None,
                   method: str | None = None) -> dict:
    """Build an interpretation-layer semantic statement.

    Auxiliary defaults to ``hasAssessment``. The ``confidence`` lives in
    the explanation box, as in Heckmann's original.
    """
    explanation: dict[str, Any] = {"confidence": confidence}
    if creator:
        explanation["creator"] = creator
    if method:
        explanation["method"] = method
    return _statement("interpretation", subject, "hasAssessment", predicate,
                      value, explanation=explanation)


def situation(subject: str, situation_type: str, start: str | None = None,
              end: str | None = None, confidence: float = 0.9) -> dict:
    """Build a situation-layer semantic statement.

    Mirrors Heckmann's ``isInSituation`` idiom: auxiliary is ``isInSituation``,
    predicate is ``activity``, range is the situation label.  Temporal scope
    goes into the situation-box, confidence into the explanation-box.
    """
    sit_box = {}
    if start:
        sit_box["start"] = start
    if end:
        sit_box["end"] = end
    return _statement(
        "situation", subject, "isInSituation", "activity", situation_type,
        situation=sit_box or None,
        explanation={"confidence": confidence},
    )


def application(subject: str, predicate: str, value: Any,
                auxiliary: str = "hasPolicy") -> dict:
    """Build an application-layer semantic statement.

    Auxiliary defaults to ``hasPolicy`` (domain-decision modality); callers may
    override for other application semantics.
    """
    return _statement("application", subject, auxiliary, predicate, value)


def sample_smart_office(user_id: str, now_iso: str) -> list[dict]:
    """Smart-office scenario as a v0.4 flat list of semantic statements."""
    return [
        observation(user_id, "temperature", 22.3, source="sensor:thermostat-01"),
        observation(user_id, "location", "ConferenceRoomA", source="sensor:rfid-03"),
        interpretation(user_id, "thermalComfort", "comfortable", confidence=0.92,
                       creator="did:example:comfort-agent", method="thermal_model_v1"),
        situation(user_id, "meeting", start=now_iso, confidence=0.95),
    ]
