"""Shared pytest fixtures and configurations for the Wha7 application.

This module provides test fixtures and configurations used across all test files,
including:
- Database session management
- Mock services
- Test data fixtures
- Test client setup
- Authentication fixtures
"""

import pytest
from typing import AsyncGenerator, Generator
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import base64
import httpx

from app.main import app
from app.core.config import get_settings
from app.database.session import get_session
from app.models.database.base import Base
from app.models.database.user import PhoneNumber
from app.models.database.outfit import Outfit, Item, Link
from app.core.security import create_access_token

# Test settings
settings = get_settings()
TEST_DATABASE_URL = settings.DATABASE_URL + "_test"

# Create test database engine
engine = create_async_engine(TEST_DATABASE_URL, echo=True)
TestingSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Event loop fixture
@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

# Database fixtures
@pytest.fixture(scope="session")
async def test_db():
    """Create test database schema."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def db_session(test_db) -> AsyncGenerator[AsyncSession, None]:
    """Get database session for testing."""
    async with TestingSessionLocal() as session:
        yield session
        # Rollback after each test
        await session.rollback()

# FastAPI test client
@pytest.fixture
def client(db_session: AsyncSession) -> Generator[TestClient, None, None]:
    """Get test client."""
    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

# Test user fixtures
@pytest.fixture
async def test_user(db_session: AsyncSession) -> PhoneNumber:
    """Create test user."""
    user = PhoneNumber(
        phone_number="+11234567890",
        is_activated=True,
        instagram_username="test_user"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest.fixture
def test_user_token(test_user: PhoneNumber) -> str:
    """Create authentication token for test user."""
    return create_access_token({"sub": str(test_user.id)})

# Test outfit fixtures
@pytest.fixture
async def test_outfit(db_session: AsyncSession, test_user: PhoneNumber) -> Outfit:
    """Create test outfit."""
    outfit = Outfit(
        phone_id=test_user.id,
        description="Test outfit",
        image_data="test_image_data"
    )
    db_session.add(outfit)
    await db_session.commit()
    await db_session.refresh(outfit)
    return outfit

@pytest.fixture
async def test_item(db_session: AsyncSession, test_outfit: Outfit) -> Item:
    """Create test item."""
    item = Item(
        outfit_id=test_outfit.id,
        description="Test item",
        search="test item search"
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    return item

# Mock service fixtures
@pytest.fixture
def mock_ai_service(mocker):
    """Mock AI processing service."""
    return mocker.patch("app.services.ai_processing.AIService")

@pytest.fixture
def mock_image_service(mocker):
    """Mock image processing service."""
    return mocker.patch("app.services.image_processing.ImageProcessingService")

@pytest.fixture
def mock_social_service(mocker):
    """Mock social media service."""
    return mocker.patch("app.services.social_media.SocialMediaService")

# Test data fixtures
@pytest.fixture
def test_image() -> str:
    """Get base64 encoded test image."""
    return "data:image/jpeg;base64," + base64.b64encode(b"test_image").decode()

@pytest.fixture
def auth_headers(test_user_token: str) -> dict:
    """Get authentication headers."""
    return {"Authorization": f"Bearer {test_user_token}"}

# HTTP client fixtures
@pytest.fixture
async def async_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Get async HTTP client."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        yield client

# Clean up after tests
@pytest.fixture(autouse=True)
async def cleanup_after_test(db_session: AsyncSession):
    """Clean up after each test."""
    yield
    # Clean up any test data
    await db_session.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        await db_session.execute(table.delete())
    await db_session.commit()