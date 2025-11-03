# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a production-ready Model Context Protocol (MCP) server for Donetick chores management. It enables Claude and other MCP-compatible AI assistants to interact with a Donetick instance through a secure, rate-limited API.

**Key Technologies:**
- Python 3.11+
- MCP SDK (>=1.20.0)
- httpx for async HTTP
- Pydantic for data validation
- Docker for containerization

## Development Commands

### Setup & Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install for development
pip install -e ".[dev]"

# Install production only
pip install -e .
```

### Running the Server

```bash
# Run directly with Python
python -m donetick_mcp.server

# Or use entry point
donetick-mcp

# Run with Docker
docker-compose up -d

# View Docker logs
docker-compose logs -f donetick-mcp

# Stop Docker
docker-compose down
```

### Testing

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_client.py
pytest tests/test_server.py

# Run with coverage
pytest --cov=donetick_mcp --cov-report=html

# Run single test
pytest tests/test_client.py::test_list_chores -v
```

### Linting & Formatting

```bash
# Check code with ruff
ruff check src/

# Format code with ruff
ruff format src/
```

## Architecture

### High-Level Structure

The codebase follows a clean separation of concerns:

```
┌─────────────────┐
│   MCP Server    │ ← server.py: Exposes 5 tools to Claude
│   (server.py)   │   Handles tool registration & execution
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Donetick API   │ ← client.py: HTTP client wrapper
│  Client         │   Rate limiting, retry logic, auth
│  (client.py)    │   Connection pooling
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Pydantic       │ ← models.py: Type-safe data models
│  Models         │   Request/response validation
│  (models.py)    │
└─────────────────┘
```

### Key Components

#### 1. MCP Server (server.py)

- **Purpose**: Exposes Donetick functionality as MCP tools
- **Transport**: stdio (for Claude Desktop integration)
- **Global State**: Maintains a single `DonetickClient` instance
- **Tools Exposed**:
  - `list_chores`: List with filters (active status, assigned user)
  - `get_chore`: Get by ID (uses client-side filtering)
  - `create_chore`: Create new chore
  - `complete_chore`: Mark complete (Premium feature)
  - `delete_chore`: Delete chore (creator only)

**Important**: The server uses a global client instance for connection pooling. Call `cleanup()` on shutdown to properly close resources.

#### 2. API Client (client.py)

- **HTTP Client**: Uses `httpx.AsyncClient` with connection pooling
- **Rate Limiting**: Token bucket algorithm (default: 10 req/sec)
- **Retry Logic**: Exponential backoff with jitter for 5xx errors and 429
- **Authentication**: Uses `secretkey` header (NOT standard Bearer token)
- **Context Manager**: Supports async with for resource cleanup

**Key Implementation Details**:
- Connection pool: max 100 connections, 20 keepalive
- Timeouts: 5s connect, 30s read, 5s write
- No retry on 4xx errors (except 429 rate limits)
- Client-side filtering for `get_chore` (API lacks GET by ID endpoint)

#### 3. Data Models (models.py)

All API interactions use Pydantic models for type safety:

- **ChoreCreate**: For creating chores (uses PascalCase field names: `Name`, `Description`, `DueDate`, `CreatedBy`)
- **ChoreUpdate**: For updating chores (uses camelCase: `name`, `description`, `nextDueDate`)
- **Chore**: Complete chore model with all metadata
- **CircleMember**: Circle/household member details

**Critical Note**: The Donetick API uses inconsistent casing between create and update operations. ChoreCreate uses PascalCase while ChoreUpdate uses camelCase.

#### 4. Configuration (config.py)

Loads from environment variables via `.env` file:
- `DONETICK_BASE_URL` (required): Instance URL
- `DONETICK_API_TOKEN` (required): API token from Settings > Access Token
- `LOG_LEVEL` (optional): DEBUG, INFO, WARNING, ERROR
- `RATE_LIMIT_PER_SECOND` (optional): Default 10.0
- `RATE_LIMIT_BURST` (optional): Default 10

## Donetick API Quirks & Gotchas

### 1. Authentication Header
Use `secretkey` header, NOT standard `Authorization: Bearer`:
```python
headers = {"secretkey": api_token}
```

### 2. Missing GET by ID Endpoint
The API doesn't support `GET /eapi/v1/chore/:id`. Instead:
- Fetch all chores with `GET /eapi/v1/chore`
- Filter client-side by ID
- Implementation in `client.py:get_chore()`

### 3. Premium Features
These operations require Donetick Plus membership:
- `complete_chore` (POST /eapi/v1/chore/:id/complete)
- `update_chore` (PUT /eapi/v1/chore/:id)
- `get_circle_members` (GET /eapi/v1/circle/members)

### 4. Field Name Inconsistency
- **Create**: PascalCase (`Name`, `Description`, `DueDate`, `CreatedBy`)
- **Update**: camelCase (`name`, `description`, `nextDueDate`)
- **Response**: camelCase for all fields

### 5. Date Format
Accepts both formats:
- ISO date: `2025-11-10`
- RFC3339: `2025-11-10T00:00:00Z`

## Testing Strategy

The test suite uses mocked HTTP responses (pytest-httpx) to avoid hitting the real API:

1. **Unit Tests** (test_client.py): Test each API method in isolation
   - Rate limiting behavior
   - Retry logic with exponential backoff
   - Error handling (4xx, 5xx, timeouts)
   - Client-side filtering for get_chore

2. **Integration Tests** (test_server.py): Test MCP tool execution
   - Tool registration
   - Tool invocation with various parameters
   - Error responses
   - JSON serialization

**Running Tests Without Real API**:
Tests are fully mocked and don't require a Donetick instance. The `.env` file is not needed for testing.

## Common Development Tasks

### Adding a New Tool

1. Add tool definition to `server.py:list_tools()`
2. Add handler in `server.py:call_tool()`
3. Add corresponding method to `client.py:DonetickClient`
4. Create Pydantic models if needed in `models.py`
5. Add tests in `tests/test_server.py` and `tests/test_client.py`

### Modifying Rate Limits

Rate limiting is configured in two places:
- **Default**: `config.py` (10 req/sec)
- **Override**: Environment variables or `DonetickClient` constructor

The token bucket refills continuously, so burst capacity = sustained rate.

### Debugging API Issues

Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
python -m donetick_mcp.server
```

This logs:
- Every HTTP request (method, URL, attempt number)
- Rate limiting waits
- Retry backoff delays
- Response status codes

### Understanding the Async Context

The client uses async/await throughout:
- Always use `await client.method()` for API calls
- The global client is created lazily on first `get_client()` call
- Call `await cleanup()` on server shutdown to close connections
- Tests use `pytest-asyncio` with `asyncio_mode = "auto"`

## Docker Deployment

The Dockerfile uses multi-stage builds:
1. **Base**: Python 3.11-slim with system dependencies
2. **Builder**: Installs Python packages
3. **Runtime**: Non-root user, minimal attack surface

Security features:
- Runs as non-root user (UID 1000)
- `no-new-privileges` security option
- Resource limits (1 CPU, 512MB RAM)
- Optional read-only filesystem

## Claude Desktop Integration

Add to `~/.config/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "donetick": {
      "command": "docker",
      "args": [
        "exec", "-i", "donetick-mcp-server",
        "python", "-m", "donetick_mcp.server"
      ]
    }
  }
}
```

Or for Python direct:
```json
{
  "mcpServers": {
    "donetick": {
      "command": "python",
      "args": ["-m", "donetick_mcp.server"],
      "env": {
        "DONETICK_BASE_URL": "https://your-instance.com",
        "DONETICK_API_TOKEN": "your_token"
      }
    }
  }
}
```

## Important File Locations

- `src/donetick_mcp/server.py:34-150` - Tool definitions
- `src/donetick_mcp/server.py:153-252` - Tool handlers
- `src/donetick_mcp/client.py:118-199` - HTTP retry logic
- `src/donetick_mcp/client.py:17-56` - Token bucket rate limiter
- `src/donetick_mcp/models.py:29-48` - ChoreCreate model (note PascalCase)
- `src/donetick_mcp/models.py:68-136` - Complete Chore model
- `tests/test_client.py` - Client unit tests with mocked HTTP
- `tests/test_server.py` - MCP server integration tests

## Recent Enhancements

### Security Improvements
1. **HTTPS Enforcement**: Config validation ensures all connections use HTTPS
2. **Sanitized Logging**: URLs and sensitive data are redacted from logs
3. **Secure Error Messages**: Error responses to users don't leak internal details
4. **Input Validation**: All user inputs are validated and sanitized
5. **Certificate Verification**: HTTPS certificates are verified by default
6. **Proper Cleanup**: Fixed resource leak in server shutdown

### Performance Improvements
1. **Smart Caching**: `get_chore` now caches results for 60 seconds (configurable)
2. **Optimized Connections**: Increased keepalive connections from 20 to 50
3. **Extended Keepalive**: Connection expiry increased from 5s to 30s

### Feature Completeness
1. **100% API Coverage**: All 24 chore creation parameters now supported
2. **Field Validation**: Pydantic validators for dates, frequency types, strategies
3. **Input Sanitization**: Control character removal, length limits
4. **Enhanced Error Handling**: Specific error messages for different HTTP status codes

## Known Limitations

1. **No GET by ID**: Must fetch all chores and filter (mitigated by caching)
2. **No Pagination**: API returns all chores in single response
3. **Premium Required**: Complete and update operations need Plus membership
4. **Circle Scoped**: All operations are scoped to the user's circle/household
