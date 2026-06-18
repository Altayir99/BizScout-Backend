from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.message import Message
from app.models.session import ChatSession
from app.config import get_settings
from datetime import datetime, timezone

settings = get_settings()


async def get_session_history(db: AsyncSession, session_id: str) -> list[dict]:
    """Return last N messages for a session as Claude-compatible dicts."""
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.desc())
        .limit(settings.memory_window)
    )
    messages = result.scalars().all()
    # Reverse to chronological order
    return [{"role": m.role, "content": m.content} for m in reversed(messages)]


async def save_messages(db: AsyncSession, session_id: str, user_msg: str, assistant_msg: str):
    """Persist both turns in one DB write."""
    db.add(Message(session_id=session_id, role="user", content=user_msg))
    db.add(Message(session_id=session_id, role="assistant", content=assistant_msg))
    
    session = await db.get(ChatSession, session_id)
    if session:
        if session.title == "Neue Unterhaltung":
            clean = user_msg.strip().replace("\n", " ")
            session.title = (clean[:57] + "…") if len(clean) > 60 else clean
        session.updated_at = datetime.now(timezone.utc)
    
    await db.commit()


async def create_session(db: AsyncSession, title: str = "Neue Unterhaltung") -> ChatSession:
    session = ChatSession(title=title)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_or_create_session(db: AsyncSession, session_id: str | None) -> ChatSession:
    if session_id:
        result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
        session = result.scalar_one_or_none()
        if session:
            return session
    return await create_session(db)
