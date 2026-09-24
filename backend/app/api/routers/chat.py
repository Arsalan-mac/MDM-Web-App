import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_db
from app.cleansing.agent_service import AgentNotConfigured, chat

router = APIRouter(prefix="/projects/{project_id}/chat", tags=["chat"])


class ChatTurn(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatTurn] = []


class ChatResponse(BaseModel):
    reply: str


@router.post("", response_model=ChatResponse)
async def send_message(
    project_id: uuid.UUID,
    payload: ChatRequest,
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    """Ask the read-only "talk to your data" agent a question about this
    project. `history` is the prior turns of this conversation (kept
    client-side - see app/cleansing/agent_service.py); the client appends
    both the user's message and this response to it for the next call.
    """
    try:
        reply = await chat(
            db,
            project_id,
            payload.message,
            [turn.model_dump() for turn in payload.history],
        )
    except AgentNotConfigured as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    return {"reply": reply}
