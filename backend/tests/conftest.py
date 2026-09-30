import os
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings

pytest_plugins = ("pytest_asyncio",)


@pytest.fixture(autouse=True, scope="session")
def enforce_test_environment_and_emulator_safety():
    """
    Strict safety preflight fixture:
    1. Sets ENVIRONMENT='test'.
    2. Overrides FIREBASE_PROJECT_ID to 'test-project-emulator' if not already configured.
    3. Fails loudly if pointed at production Firestore ('resumeiq-3cfe6') without FIRESTORE_EMULATOR_HOST.
    """
    os.environ["ENVIRONMENT"] = "test"
    settings.ENVIRONMENT = "test"

    emulator_host = os.environ.get("FIRESTORE_EMULATOR_HOST")
    if settings.FIREBASE_PROJECT_ID == "resumeiq-3cfe6" and not emulator_host:
        # Default tests safely to test project
        settings.FIREBASE_PROJECT_ID = "test-resumeiq-emulator"

    yield


@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

