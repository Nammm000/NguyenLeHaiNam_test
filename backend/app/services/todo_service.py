import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tag import Tag
from app.models.todo import Todo
from app.models.todo_tag import TodoTag
from app.schemas.todo import TodoCreate


def _escape_like(keyword: str) -> str:
    return keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def create_todo(
    db: AsyncSession, todo_data: TodoCreate, user_id: uuid.UUID
) -> Todo:
    todo = Todo(
        title=todo_data.title,
        description=todo_data.description,
        user_id=user_id,
    )
    db.add(todo)
    await db.flush()
    await db.refresh(todo)
    return todo


async def get_todos(
    db: AsyncSession,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
    status: str | None = None,
    tag_id: uuid.UUID | None = None,
    keyword: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[list[Todo], int]:
    """Get the user's todos with filtering and pagination."""
    conditions = [Todo.user_id == user_id]

    if status is not None:
        conditions.append(Todo.completed == (status == "completed"))
    if keyword:
        pattern = f"%{_escape_like(keyword)}%"
        conditions.append(
            or_(
                Todo.title.ilike(pattern, escape="\\"),
                Todo.description.ilike(pattern, escape="\\"),
            )
        )
    if tag_id is not None:
        conditions.append(
            Todo.id.in_(select(TodoTag.todo_id).where(TodoTag.tag_id == tag_id))
        )
    if date_from is not None:
        conditions.append(
            Todo.created_at
            >= datetime.combine(date_from, time.min, tzinfo=timezone.utc)
        )
    if date_to is not None:
        conditions.append(
            Todo.created_at <= datetime.combine(date_to, time.max, tzinfo=timezone.utc)
        )

    query = (
        select(Todo)
        .where(*conditions)
        .order_by(Todo.created_at.desc(), Todo.id.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    todos = list(result.scalars().all())

    count_query = select(func.count()).select_from(Todo).where(*conditions)
    total = await db.execute(count_query)

    return todos, total.scalar_one()


async def get_todo_by_id(db: AsyncSession, todo_id: uuid.UUID) -> Todo | None:
    result = await db.execute(select(Todo).where(Todo.id == todo_id))
    return result.scalar_one_or_none()


async def update_todo(db: AsyncSession, todo: Todo, update_data: dict) -> Todo:
    for key, value in update_data.items():
        setattr(todo, key, value)
    await db.flush()
    await db.refresh(todo)
    return todo


async def delete_todo(db: AsyncSession, todo: Todo) -> None:
    await db.delete(todo)
    await db.flush()


async def attach_tag(db: AsyncSession, todo: Todo, tag: Tag) -> bool:
    """Attach a tag to a todo. Returns False when already attached."""
    existing = await db.execute(
        select(TodoTag).where(TodoTag.todo_id == todo.id, TodoTag.tag_id == tag.id)
    )
    if existing.scalar_one_or_none() is not None:
        return False
    db.add(TodoTag(todo_id=todo.id, tag_id=tag.id))
    await db.flush()
    return True


async def detach_tag(db: AsyncSession, todo: Todo, tag_id: uuid.UUID) -> bool:
    """Detach a tag from a todo. Returns False when not attached."""
    result = await db.execute(
        delete(TodoTag).where(TodoTag.todo_id == todo.id, TodoTag.tag_id == tag_id)
    )
    await db.flush()
    return result.rowcount > 0


async def bulk_update_status(
    db: AsyncSession,
    user_id: uuid.UUID,
    todo_ids: list[uuid.UUID],
    completed: bool,
) -> int:
    """Update many todos' status in one transaction, scoped to the owner.

    Ids not owned by the user (or nonexistent) are silently skipped so the
    response leaks nothing about other users' data.
    """
    result = await db.execute(
        update(Todo)
        .where(Todo.user_id == user_id, Todo.id.in_(todo_ids))
        .values(completed=completed, updated_at=datetime.now(timezone.utc))
    )
    await db.flush()
    return result.rowcount
