import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.tag import Tag
    from app.models.user import User


class Todo(Base):
    """Todo model."""

    __tablename__ = "todos"
    __table_args__ = (
        # Serves status-filtered list queries (WHERE user_id AND completed).
        Index(
            "ix_todos_user_completed_created_at",
            "user_id",
            "completed",
            "created_at",
        ),
        # Serves the default list ORDER BY created_at DESC, id DESC
        # (backward index scan, no sort node).
        Index("ix_todos_user_created_id", "user_id", "created_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
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

    # Relationships
    user: Mapped["User"] = relationship(  # noqa: F821
        "User",
        back_populates="todos",
        lazy="select",
    )
    tags: Mapped[list["Tag"]] = relationship(  # noqa: F821
        "Tag",
        secondary="todo_tags",
        back_populates="todos",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Todo {self.title}>"
