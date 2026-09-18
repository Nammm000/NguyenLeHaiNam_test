import json
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_redis
from app.core.redis import RedisClient
from app.db.session import get_db
from app.models.user import User
from app.schemas.tag import TagAttachRequest
from app.schemas.todo import (
    BulkStatusRequest,
    BulkStatusResponse,
    TodoCreate,
    TodoListResponse,
    TodoResponse,
    TodoUpdate,
)
from app.services import tag_service
from app.services.todo_service import (
    attach_tag,
    bulk_update_status,
    create_todo,
    delete_todo,
    detach_tag,
    get_todo_by_id,
    get_todos,
    update_todo,
)

router = APIRouter()

CACHE_TTL = 300  # 5 minutes


def build_list_cache_key(
    user_id: uuid.UUID,
    page: int,
    page_size: int,
    status_filter: str | None,
    tag_id: uuid.UUID | None,
    keyword: str | None,
    date_from: date | None,
    date_to: date | None,
) -> str:
    """Cache key scoped by user AND every filter parameter."""
    return (
        f"todos:list:{user_id}:p{page}:n{page_size}"
        f":st={status_filter or 'all'}"
        f":tag={tag_id or 'any'}"
        f":kw={keyword or 'all'}"
        f":df={date_from or 'all'}"
        f":dt={date_to or 'all'}"
    )


async def invalidate_list_cache(redis: RedisClient, user_id: uuid.UUID) -> None:
    await redis.delete_pattern(f"todos:list:{user_id}:*")


@router.get("", response_model=TodoListResponse)
async def list_todos(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    size: int | None = Query(None, ge=1, le=200, deprecated=True),
    status_filter: str | None = Query(
        None, alias="status", pattern="^(completed|active)$"
    ),
    tag_id: uuid.UUID | None = Query(None),
    keyword: str | None = Query(None, min_length=1, max_length=200),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Get the user's todos with filtering and pagination."""
    if size is not None and size != page_size:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="'size' is a deprecated alias of 'page_size' "
            "and must match it when both are provided",
        )
    effective_size = size if size is not None else page_size
    skip = (page - 1) * effective_size

    cache_key = build_list_cache_key(
        current_user.id,
        page,
        effective_size,
        status_filter,
        tag_id,
        keyword,
        date_from,
        date_to,
    )

    cached = await redis.get(cache_key)
    if cached:
        cached_data = json.loads(cached)
        return TodoListResponse(**cached_data)

    todos, total = await get_todos(
        db,
        user_id=current_user.id,
        skip=skip,
        limit=effective_size,
        status=status_filter,
        tag_id=tag_id,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
    )

    items = []
    for todo in todos:
        item = TodoResponse.model_validate(todo)
        # Every todo in this list belongs to the caller by construction.
        item.user_email = current_user.email
        items.append(item)

    response = TodoListResponse(
        items=items,
        total=total,
        page=page,
        size=effective_size,
    )

    await redis.set(cache_key, response.model_dump_json(), ex=CACHE_TTL)

    return response


@router.post("", response_model=TodoResponse, status_code=status.HTTP_201_CREATED)
async def create_new_todo(
    todo_data: TodoCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Create a todo item."""
    todo = await create_todo(db, todo_data, current_user.id)
    await invalidate_list_cache(redis, current_user.id)
    return todo


@router.patch("/bulk-status", response_model=BulkStatusResponse)
async def bulk_update_todo_status(
    bulk_data: BulkStatusRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Bulk update todo status in a single transaction (own todos only)."""
    updated = await bulk_update_status(
        db, current_user.id, bulk_data.todo_ids, bulk_data.completed
    )
    await invalidate_list_cache(redis, current_user.id)
    return BulkStatusResponse(updated=updated, requested=len(bulk_data.todo_ids))


@router.get("/{todo_id}", response_model=TodoResponse)
async def get_todo(
    todo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific todo by ID."""
    todo = await get_todo_by_id(db, todo_id)
    if not todo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found",
        )
    if todo.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this todo",
        )

    return todo


@router.put("/{todo_id}", response_model=TodoResponse)
async def update_existing_todo(
    todo_id: uuid.UUID,
    todo_data: TodoUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Update a todo item."""
    todo = await get_todo_by_id(db, todo_id)
    if not todo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found",
        )
    if todo.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this todo",
        )

    update_data = todo_data.model_dump(exclude_unset=True)

    updated_todo = await update_todo(db, todo, update_data)
    await invalidate_list_cache(redis, current_user.id)

    return updated_todo


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_todo(
    todo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Delete a todo item."""
    todo = await get_todo_by_id(db, todo_id)
    if not todo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found",
        )
    if todo.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this todo",
        )

    await delete_todo(db, todo)
    await invalidate_list_cache(redis, current_user.id)

    return None


@router.post("/{todo_id}/tags", response_model=TodoResponse)
async def attach_tag_to_todo(
    todo_id: uuid.UUID,
    body: TagAttachRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Attach one of the user's own tags to one of the user's own todos."""
    todo = await get_todo_by_id(db, todo_id)
    if not todo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found",
        )
    if todo.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this todo",
        )

    tag = await tag_service.get_tag_by_id(db, body.tag_id)
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found",
        )
    if tag.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to use this tag",
        )

    created = await attach_tag(db, todo, tag)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    await db.refresh(todo)
    await invalidate_list_cache(redis, current_user.id)
    return todo


@router.delete("/{todo_id}/tags/{tag_id}", response_model=TodoResponse)
async def detach_tag_from_todo(
    todo_id: uuid.UUID,
    tag_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Detach a tag from a todo."""
    todo = await get_todo_by_id(db, todo_id)
    if not todo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found",
        )
    if todo.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this todo",
        )

    detached = await detach_tag(db, todo, tag_id)
    if not detached:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag is not attached to this todo",
        )

    await db.refresh(todo)
    await invalidate_list_cache(redis, current_user.id)
    return todo
