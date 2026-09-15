import os
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database import Base, get_db
import app.database as db_module
from app.main import app

TEST_DB_PATH = "storage/test_isolated.db"
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
    TestSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False
    )

    # Patch db_module engine and AsyncSessionLocal
    orig_engine = db_module.engine
    orig_session = db_module.AsyncSessionLocal
    db_module.engine = test_engine
    db_module.AsyncSessionLocal = TestSessionLocal

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with TestSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db

    yield

    # Cleanup
    app.dependency_overrides.clear()
    await test_engine.dispose()
    db_module.engine = orig_engine
    db_module.AsyncSessionLocal = orig_session
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass
