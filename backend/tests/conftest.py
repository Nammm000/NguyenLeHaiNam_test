import asyncio
import fnmatch
import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Use SQLite for tests before app modules initialize their default engine.
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.api.deps import get_redis  # noqa: E402
from app.core.security import create_access_token, get_password_hash  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_maker = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class FakeRedis:
    """Dict-backed stand-in covering the RedisClient surface used by the app."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)

    async def delete_pattern(self, pattern: str) -> None:
        for key in [k for k in self.store if fnmatch.fnmatch(k, pattern)]:
            del self.store[key]

    async def exists(self, key: str) -> bool:
        return key in self.store


fake_redis = FakeRedis()


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    fake_redis.store.clear()
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with test_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def override_get_redis() -> FakeRedis:
    return fake_redis


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_redis] = override_get_redis


async def create_test_user(email: str, password: str = "Test@1234") -> User:
    """Insert a user row so tokens minted for it resolve in get_current_user."""
    async with test_session_maker() as session:
        user = User(email=email, hashed_password=get_password_hash(password))
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


def auth_headers_for(user: User) -> dict:
    token = create_access_token(data={"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_session_maker() as session:
        yield session


@pytest.fixture
def redis_store() -> dict[str, str]:
    return fake_redis.store


@pytest.fixture
async def user_a() -> User:
    return await create_test_user("a@test.com")


@pytest.fixture
async def user_b() -> User:
    return await create_test_user("b@test.com")


@pytest.fixture
def auth_headers(user_a: User) -> dict:
    return auth_headers_for(user_a)


@pytest.fixture
def auth_headers_a(user_a: User) -> dict:
    return auth_headers_for(user_a)


@pytest.fixture
def auth_headers_b(user_b: User) -> dict:
    return auth_headers_for(user_b)
