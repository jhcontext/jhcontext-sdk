"""Provenance API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...prov import PROVGraph
from ..app import get_storage

router = APIRouter()


class PROVSubmitRequest(BaseModel):
    context_id: str
    graph_turtle: str


class PROVQueryRequest(BaseModel):
    context_id: str
    query_type: str  # causal_chain, used_entities, temporal_sequence
    entity_id: str | None = None


@router.post("", status_code=201)
async def submit_prov_graph(req: PROVSubmitRequest):
    from ...crypto import compute_sha256

    digest = compute_sha256(req.graph_turtle.encode("utf-8"))
    storage = get_storage()
    path = storage.save_prov_graph(req.context_id, req.graph_turtle, digest)
    return {"context_id": req.context_id, "digest": digest, "path": path}


@router.get("/{context_id}")
async def get_prov_graph(context_id: str):
    storage = get_storage()
    turtle = storage.get_prov_graph(context_id)
    if not turtle:
        raise HTTPException(status_code=404, detail="PROV graph not found")
    return {"context_id": context_id, "graph_turtle": turtle}


@router.post("/query")
async def query_provenance(req: PROVQueryRequest):
    storage = get_storage()
    turtle = storage.get_prov_graph(req.context_id)
    if not turtle:
        raise HTTPException(status_code=404, detail="PROV graph not found")

    prov = PROVGraph(context_id=req.context_id)
    prov._graph.parse(data=turtle, format="turtle")

    if req.query_type == "causal_chain" and req.entity_id:
        chain = prov.get_causal_chain(req.entity_id)
        return {"query_type": "causal_chain", "entity_id": req.entity_id, "chain": chain}
    elif req.query_type == "used_entities" and req.entity_id:
        used = prov.get_used_entities(req.entity_id)
        return {"query_type": "used_entities", "activity_id": req.entity_id, "entities": used}
    elif req.query_type == "temporal_sequence":
        seq = prov.get_temporal_sequence()
        return {"query_type": "temporal_sequence", "activities": seq}
    else:
        raise HTTPException(status_code=400, detail=f"Unknown query_type: {req.query_type}")
