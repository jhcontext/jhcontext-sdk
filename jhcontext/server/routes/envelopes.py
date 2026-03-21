"""Envelope API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...models import Envelope
from ...pii import DefaultPIIDetector, detach_pii
from ..app import get_storage, get_pii_vault

router = APIRouter()


class EnvelopeSubmitRequest(BaseModel):
    envelope: dict


@router.post("", status_code=201)
async def submit_envelope(req: EnvelopeSubmitRequest):
    data = req.envelope
    data.pop("@context", None)
    data.pop("@type", None)
    envelope = Envelope.model_validate(data)

    # Enforce PII detachment if feature_suppression is set
    if envelope.privacy.feature_suppression and not envelope.privacy.pii_detached:
        vault = get_pii_vault()
        if vault is not None:
            detector = DefaultPIIDetector(
                suppressed_fields=envelope.privacy.feature_suppression,
            )
            envelope.semantic_payload = detach_pii(
                envelope.semantic_payload,
                envelope.context_id,
                detector,
                vault,
            )
            envelope.privacy.pii_detached = True

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


@router.delete("/{context_id}/pii")
async def purge_pii(context_id: str):
    """Purge all PII associated with a context (GDPR Art. 17 erasure)."""
    vault = get_pii_vault()
    if vault is None:
        raise HTTPException(status_code=501, detail="PII vault not configured")
    deleted = vault.purge_by_context(context_id)
    return {"context_id": context_id, "tokens_purged": deleted}
