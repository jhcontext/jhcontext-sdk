"""UserML SituationalStatement helpers for the jhcontext SDK (protocol v0.5).

Each function returns one atomic **SituationalStatement** (also called a
"semantic statement" in PAC-AI prose) — a single entry of an envelope's
``semantic_payload``, which is itself a **SituationReport** (bag of
SituationalStatements) in Heckmann (2005)'s sense.

Per-statement shape, corrected to Heckmann's onion model:

- ``@model``        — discriminator, ``"UserML"``
- ``mainpart``      — five-tuple: ``subject``, ``auxiliary``, ``predicate``,
                      ``range`` (value-space / type), ``object`` (actual value)
- ``situation``     — *(optional)* temporal/spatial box:
                      ``start``, ``end``, ``durability``, ``location``, ``position``
- ``explanation``   — *(optional)* epistemic metadata:
                      ``source``, ``creator``, ``method``, ``evidence``, ``confidence``
- ``administration``— ``group`` classifier (open string; PAC-AI uses
                      ``Observation``/``Interpretation``/``Situation``/``Application``)

Heckmann's ``privacy`` box is factored to envelope-level governance and is
omitted per-statement. ``administration.id``/``unique``/``replaces`` overlap
with envelope ``context_id`` and the ``proof`` block and are omitted too.

v0.5 replaces the v0.4 top-level ``layer`` type-tag with the native
``administration.group`` slot — the ``layer`` field was not in Heckmann
(per ORACON §4.1).
"""

from typing import Any


def _statement(group: str, subject: str, auxiliary: str, predicate: str,
               object_: Any, range_: str | None = None,
               situation: dict | None = None,
               explanation: dict | None = None) -> dict:
    mainpart: dict[str, Any] = {
        "subject":   subject,
        "auxiliary": auxiliary,
        "predicate": predicate,
    }
    if range_ is not None:
        mainpart["range"] = range_
    mainpart["object"] = object_

    stmt: dict[str, Any] = {
        "@model":         "UserML",
        "mainpart":       mainpart,
        "administration": {"group": group},
    }
    if situation:
        stmt["situation"] = situation
    if explanation:
        stmt["explanation"] = explanation
    return stmt


def observation(subject: str, predicate: str, object_: Any,
                range_: str | None = None,
                source: str | None = None) -> dict:
    """Build an Observation-group SituationalStatement.

    Auxiliary defaults to ``hasProperty`` — the neutral modal operator for
    direct sensor/metadata facts. Observations usually don't need
    ``explanation.confidence`` (they are direct) but often carry
    ``explanation.source`` (the sensor / origin).
    """
    explanation = {"source": source} if source else None
    return _statement("Observation", subject, "hasProperty", predicate,
                      object_, range_=range_, explanation=explanation)


def interpretation(subject: str, predicate: str, object_: Any,
                   range_: str | None = None,
                   confidence: float = 0.9,
                   creator: str | None = None,
                   method: str | None = None) -> dict:
    """Build an Interpretation-group SituationalStatement.

    Auxiliary defaults to ``hasAssessment``. ``confidence`` lives in the
    explanation box, as in Heckmann's original.
    """
    explanation: dict[str, Any] = {"confidence": confidence}
    if creator:
        explanation["creator"] = creator
    if method:
        explanation["method"] = method
    return _statement("Interpretation", subject, "hasAssessment", predicate,
                      object_, range_=range_, explanation=explanation)


def situation(subject: str, situation_type: str,
              range_: str | None = None,
              start: str | None = None, end: str | None = None,
              durability: str | None = None,
              location: str | None = None,
              confidence: float = 0.9) -> dict:
    """Build a Situation-group SituationalStatement.

    Follows Heckmann's ``isInSituation`` idiom: auxiliary ``isInSituation``,
    predicate ``activity``, object the situation label. Temporal/spatial
    scope populates the situation box; confidence populates the explanation
    box.
    """
    sit_box = {}
    if start:
        sit_box["start"] = start
    if end:
        sit_box["end"] = end
    if durability:
        sit_box["durability"] = durability
    if location:
        sit_box["location"] = location
    return _statement(
        "Situation", subject, "isInSituation", "activity", situation_type,
        range_=range_,
        situation=sit_box or None,
        explanation={"confidence": confidence},
    )


def application(subject: str, predicate: str, object_: Any,
                range_: str | None = None,
                auxiliary: str = "hasPolicy") -> dict:
    """Build an Application-group SituationalStatement.

    Auxiliary defaults to ``hasPolicy`` (domain-decision modality); callers
    may override for other application semantics (e.g. ``hasText``,
    ``hasDecision``).
    """
    return _statement("Application", subject, auxiliary, predicate, object_,
                      range_=range_)


def userml_payload(
    observations: list[dict] | None = None,
    interpretations: list[dict] | None = None,
    situations: list[dict] | None = None,
    applications: list[dict] | None = None,
    application: list[dict] | None = None,
) -> dict:
    """Bundle UserML SituationalStatements into one SituationReport entry.

    The returned dict occupies a **single** slot in an envelope's
    ``semantic_payload``. This is the bundled-envelope variant pattern
    used by ontology helpers and several non-education scenarios (one
    envelope carrying N grouped statements without inflating envelope
    count). For the paper-canonical flat-array shape (one statement per
    ``semantic_payload`` slot, as in Figure 1 of the rubric-grounded
    feedback scenario), build a list of ``observation()`` /
    ``interpretation()`` / ``situation()`` / ``application()`` directly
    instead.

    Inputs:
      observations / interpretations: lists of statements already in UserML
        shape (built via ``observation()`` / ``interpretation()``).
      situations: shorthand dicts ``{subject, object, confidence?}``
        (``object`` is the situation type) — normalized into UserML via
        ``situation()``. The ``predicate`` key, if present, is ignored
        because UserML hardcodes ``activity`` for Situation statements.
      applications / application: shorthand dicts ``{subject, predicate,
        object, auxiliary?, range?}`` — normalized into UserML via the
        ``application()`` helper. ``application=`` is accepted for
        backward compatibility with older call sites; ``applications=``
        is preferred.
    """
    statements: list[dict] = []
    if observations:
        statements.extend(observations)
    if interpretations:
        statements.extend(interpretations)
    for s in (situations or []):
        statements.append(situation(
            subject=s["subject"],
            situation_type=s["object"],
            range_=s.get("range"),
            confidence=s.get("confidence", 0.9),
        ))
    apps_input = applications if applications is not None else application
    for a in (apps_input or []):
        statements.append(_statement(
            "Application",
            a["subject"],
            a.get("auxiliary", "hasPolicy"),
            a["predicate"],
            a["object"],
            range_=a.get("range"),
        ))
    return {
        "@model": "UserML-SituationReport",
        "statements": statements,
    }


def sample_smart_office(user_id: str, now_iso: str) -> list[dict]:
    """Smart-office scenario as a v0.5 SituationReport (list of statements)."""
    return [
        observation(user_id, "temperature", 22.3,
                    range_="float-degrees-celsius",
                    source="sensor:thermostat-01"),
        observation(user_id, "location", "ConferenceRoomA",
                    range_="LocationEnum",
                    source="sensor:rfid-03"),
        interpretation(user_id, "thermalComfort", "comfortable",
                       range_="uncomfortable-neutral-comfortable",
                       confidence=0.92,
                       creator="did:example:comfort-agent",
                       method="thermal_model_v1"),
        situation(user_id, "meeting",
                  range_="meeting|commute|idle|focus",
                  start=now_iso, durability="few minutes",
                  confidence=0.95),
    ]
