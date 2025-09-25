"""HTTP endpoints for the reservation agent."""
from __future__ import annotations

import json
from typing import Any, AsyncIterator, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.services.agent import agent_service


router = APIRouter(prefix="/agent", tags=["agent"])


class ConversationStreamRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)


class ReservationDecisionRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    action: Literal["confirm", "cancel"]
    start_time: str | None = None
    reservation_id: str | None = None


class ReservationDecisionResponse(BaseModel):
    scheduler: dict[str, Any]
    assistant_message: str


async def _json_event_stream(
    *, session_id: str, message: str
) -> AsyncIterator[bytes]:  # pragma: no cover - streaming side effects
    async for event in agent_service.stream_conversation(
        session_id=session_id, user_message=message
    ):
        yield (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")


@router.post("/chat/stream")
async def stream_conversation(
    payload: ConversationStreamRequest, settings: Settings = Depends(get_settings)
) -> StreamingResponse:
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI credentials are not configured.",
        )

    generator = _json_event_stream(
        session_id=payload.session_id,
        message=payload.message,
    )
    return StreamingResponse(generator, media_type="application/x-ndjson")


@router.post(
    "/reservations/decision",
    response_model=ReservationDecisionResponse,
)
async def decide_reservation(
    payload: ReservationDecisionRequest,
    settings: Settings = Depends(get_settings),
) -> ReservationDecisionResponse:
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI credentials are not configured.",
        )

    if payload.action == "confirm" and not payload.start_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_time is required when confirming a reservation.",
        )

    if payload.action == "cancel" and not payload.reservation_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="reservation_id is required when cancelling a reservation.",
        )

    result = await agent_service.apply_action(
        session_id=payload.session_id,
        action=payload.action,
        reservation_id=payload.reservation_id,
        start_time=payload.start_time,
    )

    return ReservationDecisionResponse(**result)
