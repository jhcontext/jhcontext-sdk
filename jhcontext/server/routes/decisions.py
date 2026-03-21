"""Decision API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any

from ...models import Decision
from ..app import get_storage

router = APIRouter()


class DecisionRequest(BaseModel):
    context_id: str
    passed_artifact_id: str | None = None
    outcome: dict[str, Any] = {}
    agent_id: str = ""


@router.post("", status_code=201)
async def log_decision(req: DecisionRequest):
    decision = Decision(
        context_id=req.context_id,
        passed_artifact_id=req.passed_artifact_id,
        outcome=req.outcome,
        agent_id=req.agent_id,
    )
    storage = get_storage()
    decision_id = storage.save_decision(decision)
    return {"decision_id": decision_id}


@router.get("/{decision_id}")
async def get_decision(decision_id: str):
    storage = get_storage()
    decision = storage.get_decision(decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    return decision.model_dump()
