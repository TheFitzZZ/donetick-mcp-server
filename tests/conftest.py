"""Pytest configuration and fixtures."""

import pytest
from pytest_httpx import HTTPXMock


@pytest.fixture(autouse=False)
async def clear_cache():
    """Clear the global client cache before tests that need isolated state."""
    from donetick_mcp.server import get_client

    # Get the global client
    client = await get_client()
    # Clear the cache
    client._chore_cache.clear()

    yield

    # Clean up after test
    client._chore_cache.clear()


@pytest.fixture
def mock_login(httpx_mock: HTTPXMock):
    """Mock the login endpoint for JWT authentication."""
    httpx_mock.add_response(
        url="https://donetick.jason1365.duckdns.org/api/v1/auth/login",
        json={"token": "test_jwt_token"},
        method="POST",
    )
    return httpx_mock
