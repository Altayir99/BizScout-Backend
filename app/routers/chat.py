from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.claude_service import ask_claude
from app.services.memory_service import get_or_create_session, get_session_history, save_messages

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    session_id: str


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    """
    AI chat with memory.
    - Creates new session if session_id is None
    - Loads last 20 messages as context for Claude
    - Saves both turns to DB
    """
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Nachricht darf nicht leer sein.")

    # 1. Get or create session
    session = await get_or_create_session(db, req.session_id)

    # 2. Load conversation history
    history = await get_session_history(db, session.id)

    # 3. Append new user message
    history.append({"role": "user", "content": req.message})

    # 4. Call Claude (HTTPException propagates with proper status codes)
    try:
        answer = await ask_claude(history)
    except HTTPException:
        raise  # Re-raise structured errors from claude_service
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Chat-Fehler: {str(e)}",
        )

    # 5. Persist both turns
    await save_messages(db, session.id, req.message, answer)

    return ChatResponse(answer=answer, session_id=session.id)
