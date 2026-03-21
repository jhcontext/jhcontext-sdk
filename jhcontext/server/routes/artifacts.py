"""Artifact API routes."""

from __future__ import annotations

import base64

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...models import Artifact, ArtifactType
from ...crypto import compute_sha256
from ..app import get_storage

router = APIRouter()


class ArtifactUploadRequest(BaseModel):
    artifact_id: str
    context_id: str
    artifact_type: str
    content_base64: str
    model: str | None = None
    deterministic: bool = False


@router.post("", status_code=201)
async def upload_artifact(req: ArtifactUploadRequest):
    content = base64.b64decode(req.content_base64)
    content_hash = compute_sha256(content)
    metadata = Artifact(
        artifact_id=req.artifact_id,
        type=ArtifactType(req.artifact_type),
        content_hash=content_hash,
        model=req.model,
        deterministic=req.deterministic,
        metadata={"context_id": req.context_id},
    )
    storage = get_storage()
    path = storage.save_artifact(req.artifact_id, content, metadata)
    return {"artifact_id": req.artifact_id, "content_hash": content_hash, "storage_path": path}


@router.get("/{artifact_id}")
async def get_artifact(artifact_id: str):
    storage = get_storage()
    result = storage.get_artifact(artifact_id)
    if not result:
        raise HTTPException(status_code=404, detail="Artifact not found")
    content, metadata = result
    return {
        "artifact_id": metadata.artifact_id,
        "type": metadata.type.value,
        "content_hash": metadata.content_hash,
        "content_base64": base64.b64encode(content).decode("utf-8"),
    }
