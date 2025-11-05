"""Live API integration tests for Donetick MCP server.

These tests interact with a real Donetick instance and are designed to verify
end-to-end functionality against the actual API. They should be run separately
from the unit tests to avoid accidental API usage.

To run live tests:
    pytest tests/integration/ -m live_api -v

To skip live tests in normal test runs:
    pytest tests/ -m "not live_api"

Requirements:
    - A running Donetick instance (accessible via HTTPS)
    - Valid credentials in .env file or environment variables
    - DONETICK_BASE_URL, DONETICK_USERNAME, DONETICK_PASSWORD
"""
