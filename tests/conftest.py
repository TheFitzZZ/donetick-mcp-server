"""Pytest configuration and fixtures."""

import pytest


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
