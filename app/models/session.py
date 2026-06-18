import uuid
from datetime import datetime, UTC
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def _utcnow() -> datetime:
    """Timezone-naive UTC now — compatible with SQLAlchemy DateTime columns."""
    return datetime.now(UTC).replace(tzinfo=None)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), default="Neue Unterhaltung")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    messages: Mapped[list["Message"]] = relationship(  # noqa: F821
        "Message", back_populates="session", cascade="all, delete-orphan", order_by="Message.created_at"
    )
