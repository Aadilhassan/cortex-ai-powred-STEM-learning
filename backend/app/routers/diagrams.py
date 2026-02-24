"""On-demand diagram generation endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(tags=["diagrams"])


# ── Request / Response models ────────────────────────────────────────────────


class DiagramRequest(BaseModel):
    topic: str
    context: str | None = None
    diagram_type: str | None = None


# ── Helpers ──────────────────────────────────────────────────────────────────


def _get_diagram_service(request: Request):
    return request.app.state.diagram_service


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/diagrams")
async def generate_diagram(body: DiagramRequest, request: Request):
    """Generate a Mermaid diagram for a given topic."""
    diagram_service = _get_diagram_service(request)

    try:
        mermaid_code = await diagram_service.generate(
            topic=body.topic,
            context=body.context,
            diagram_type=body.diagram_type,
        )
    except Exception as e:
        print(f"[diagrams] Generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Diagram generation failed. Please try again.",
        )

    return {"mermaid": mermaid_code}
