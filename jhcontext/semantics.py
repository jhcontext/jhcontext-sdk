"""Simple UserML semantics helpers for jhcontext SDK (draft).
This module provides convenience functions to create observation/interpretation/situation examples
following the UserML layered idea. These are simple JSON-friendly dict builders to be used as
semantic_payload entries in jrcontext envelopes.
"""

from typing import Dict, Any

def observation(subject: str, predicate: str, value: Any) -> Dict[str, Any]:
    return {
        "subject": subject,
        "predicate": predicate,
        "object": value
    }

def interpretation(subject: str, predicate: str, value: Any, confidence: float = 0.9) -> Dict[str, Any]:
    return {
        "subject": subject,
        "predicate": predicate,
        "object": value,
        "confidence": confidence
    }

def situation(subject: str, situation_type: str, start: str = None, end: str = None, confidence: float = 0.9) -> Dict[str, Any]:
    s = {
        "subject": subject,
        "predicate": "isInSituation",
        "object": situation_type,
        "confidence": confidence
    }
    if start:
        s["start"] = start
    if end:
        s["end"] = end
    return s

def userml_payload(observations=None, interpretations=None, situations=None, application=None):
    return {
        "@model": "UserML",
        "layers": {
            "observation": observations or [],
            "interpretation": interpretations or [],
            "situation": situations or [],
            "application": application or []
        }
    }

def sample_smart_office(user_id: str, now_iso: str):
    obs = [
        observation(user_id, "temperature", 22.3),
        observation(user_id, "location", "ConferenceRoomA")
    ]
    interp = [
        interpretation(user_id, "thermalComfort", "comfortable", confidence=0.92)
    ]
    sit = [
        situation(user_id, "meeting", start=now_iso, confidence=0.95)
    ]
    return userml_payload(observations=obs, interpretations=interp, situations=sit)
