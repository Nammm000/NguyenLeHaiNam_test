import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_redis
from app.core.redis import RedisClient
from app.db.session import get_db
from app.models.user import User
from app.schemas.tag import TagCreate, TagListResponse, TagResponse, TagUpdate
from app.services import tag_service
from app.services.tag_service import DuplicateTagNameError

router = APIRouter()


@router.get("", response_model=TagListResponse)
async def list_tags(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all tags of the authenticated user."""
    tags = await tag_service.get_tags(db, current_user.id)
    return TagListResponse(items=[TagResponse.model_validate(tag) for tag in tags])


@router.post("", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_new_tag(
    tag_data: TagCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new tag (name unique per user, case-insensitive)."""
    try:
        tag = await tag_service.create_tag(db, current_user.id, tag_data)
    except DuplicateTagNameError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    return tag


async def _get_owned_tag(db: AsyncSession, tag_id: uuid.UUID, current_user: User):
    tag = await tag_service.get_tag_by_id(db, tag_id)
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found",
        )
    if tag.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this tag",
        )
    return tag


@router.patch("/{tag_id}", response_model=TagResponse)
async def update_existing_tag(
    tag_id: uuid.UUID,
    tag_data: TagUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rename or recolor a tag."""
    tag = await _get_owned_tag(db, tag_id, current_user)
    try:
        return await tag_service.update_tag(
            db, tag, tag_data.model_dump(exclude_unset=True)
        )
    except DuplicateTagNameError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_tag(
    tag_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Delete a tag and its todo-tag relations."""
    tag = await _get_owned_tag(db, tag_id, current_user)
    await tag_service.delete_tag(db, tag)
    # Cached todo lists embed tag chips; drop them so the deleted tag
    # disappears immediately.
    await redis.delete_pattern(f"todos:list:{current_user.id}:*")
    return None
