import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.todo import Todo


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (
        # Case-insensitive unique tag name per user (functional index).
        Index("uq_tags_user_name_ci", "user_id", text("lower(name)"), unique=True),
        Index("ix_tags_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    color: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    todos: Mapped[list["Todo"]] = relationship(  # noqa: F821
        "Todo",
        secondary="todo_tags",
        back_populates="tags",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Tag {self.name}>"
