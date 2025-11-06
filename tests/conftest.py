"""Pytest configuration and fixtures."""

import pytest
from pytest_httpx import HTTPXMock


@pytest.fixture
def mock_login(httpx_mock: HTTPXMock):
    """Mock the login endpoint for JWT authentication."""
    httpx_mock.add_response(
        url="https://donetick.jason1365.duckdns.org/api/v1/auth/login",
        json={"token": "test_jwt_token"},
        method="POST",
    )
    return httpx_mock
