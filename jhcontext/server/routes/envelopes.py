"""Envelope API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...models import Envelope
from ..app import get_storage

router = APIRouter()


class EnvelopeSubmitRequest(BaseModel):
    envelope: dict


@router.post("", status_code=201)
async def submit_envelope(req: EnvelopeSubmitRequest):
    data = req.envelope
    data.pop("@context", None)
    data.pop("@type", None)
    envelope = Envelope.model_validate(data)
    storage = get_storage()
    context_id = storage.save_envelope(envelope)
    return {"context_id": context_id, "content_hash": envelope.proof.content_hash}


@router.get("/{context_id}")
async def get_envelope(context_id: str):
    storage = get_storage()
    envelope = storage.get_envelope(context_id)
    if not envelope:
        raise HTTPException(status_code=404, detail="Envelope not found")
    return envelope.to_jsonld()


@router.get("")
async def list_envelopes(scope: str | None = None, risk_level: str | None = None):
    storage = get_storage()
    filters = {}
    if scope:
        filters["scope"] = scope
    if risk_level:
        filters["risk_level"] = risk_level
    envelopes = storage.list_envelopes(**filters)
    return [{"context_id": e.context_id, "scope": e.scope, "created_at": e.created_at} for e in envelopes]
