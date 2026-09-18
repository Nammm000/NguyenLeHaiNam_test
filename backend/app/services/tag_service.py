import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tag import Tag
from app.models.todo_tag import TodoTag
from app.schemas.tag import TagCreate


class DuplicateTagNameError(ValueError):
    """Tag name already exists for the user (case-insensitive)."""


async def get_tags(db: AsyncSession, user_id: uuid.UUID) -> list[Tag]:
    result = await db.execute(
        select(Tag).where(Tag.user_id == user_id).order_by(Tag.name)
    )
    return list(result.scalars().all())


async def get_tag_by_id(db: AsyncSession, tag_id: uuid.UUID) -> Tag | None:
    result = await db.execute(select(Tag).where(Tag.id == tag_id))
    return result.scalar_one_or_none()


async def _name_taken(db: AsyncSession, user_id: uuid.UUID, name: str) -> bool:
    result = await db.execute(
        select(Tag).where(
            Tag.user_id == user_id,
            func.lower(Tag.name) == name.lower(),
        )
    )
    return result.scalar_one_or_none() is not None


async def create_tag(db: AsyncSession, user_id: uuid.UUID, tag_data: TagCreate) -> Tag:
    if await _name_taken(db, user_id, tag_data.name):
        raise DuplicateTagNameError(
            "Tag name already exists (case-insensitive) for this user"
        )
    tag = Tag(name=tag_data.name, color=tag_data.color, user_id=user_id)
    db.add(tag)
    await db.flush()
    await db.refresh(tag)
    return tag


async def update_tag(db: AsyncSession, tag: Tag, update_data: dict) -> Tag:
    new_name = update_data.get("name")
    if new_name is not None and new_name.lower() != tag.name.lower():
        if await _name_taken(db, tag.user_id, new_name):
            raise DuplicateTagNameError(
                "Tag name already exists (case-insensitive) for this user"
            )
    for key, value in update_data.items():
        setattr(tag, key, value)
    await db.flush()
    await db.refresh(tag)
    return tag


async def delete_tag(db: AsyncSession, tag: Tag) -> None:
    await db.execute(delete(TodoTag).where(TodoTag.tag_id == tag.id))
    await db.delete(tag)
    await db.flush()
