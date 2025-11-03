# Donetick MCP Server

A production-ready Model Context Protocol (MCP) server for [Donetick](https://donetick.com) chores management. Enables Claude and other MCP-compatible AI assistants to interact with your Donetick instance through a secure, rate-limited API.

## Features

- **5 Core Tools**: List, get, create, complete, and delete chores
- **Full Chore Configuration**: Support for recurrence, assignments, notifications, labels, priority, points, and more
- **Smart Caching**: Intelligent caching for get_chore operations (60s TTL by default)
- **Rate Limiting**: Token bucket algorithm prevents API overload
- **Retry Logic**: Exponential backoff with jitter for resilient operations
- **Async/Await**: Non-blocking operations using httpx
- **Input Validation**: Pydantic field validators with sanitization
- **Security Hardened**: HTTPS enforcement, sanitized logging, secure error messages
- **Docker Support**: Containerized deployment with security best practices
- **Comprehensive Testing**: Unit and integration tests with pytest
- **Type Safety**: Pydantic models for request/response validation

## Requirements

- Python 3.11 or higher
- Donetick instance (self-hosted or cloud)
- Donetick Plus/Premium membership (for complete and update operations)
- Donetick API token

## Installation

### Option 1: Docker (Recommended)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/jason1365/donetick-mcp-server.git
   cd donetick-mcp-server
   ```

2. **Create `.env` file**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Configure environment variables**:
   ```env
   DONETICK_BASE_URL=https://your-instance.com
   DONETICK_API_TOKEN=your_api_token_here
   LOG_LEVEL=INFO
   ```

4. **Build and run**:
   ```bash
   docker-compose build
   docker-compose up -d
   ```

### Option 2: Python Virtual Environment

1. **Clone and setup**:
   ```bash
   git clone https://github.com/jason1365/donetick-mcp-server.git
   cd donetick-mcp-server
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -e .
   ```

3. **Set environment variables**:
   ```bash
   export DONETICK_BASE_URL=https://your-instance.com
   export DONETICK_API_TOKEN=your_api_token_here
   ```

4. **Run the server**:
   ```bash
   python -m donetick_mcp.server
   ```

## Getting Your API Token

1. Log into your Donetick instance
2. Navigate to **Settings** → **Advanced Settings** → **Access Token**
3. Click **"Generate new token"**
4. Give it a descriptive name (e.g., "MCP Server")
5. Copy the generated token (save it securely - it won't be shown again)

## Claude Desktop Integration

Add to your Claude Desktop configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**Linux**: `~/.config/Claude/claude_desktop_config.json`

### Docker Configuration

```json
{
  "mcpServers": {
    "donetick": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "donetick-mcp-server",
        "python",
        "-m",
        "donetick_mcp.server"
      ]
    }
  }
}
```

### Python Configuration

```json
{
  "mcpServers": {
    "donetick": {
      "command": "python",
      "args": [
        "-m",
        "donetick_mcp.server"
      ],
      "env": {
        "DONETICK_BASE_URL": "https://your-instance.com",
        "DONETICK_API_TOKEN": "your_api_token_here"
      }
    }
  }
}
```

After updating the configuration, restart Claude Desktop.

## Available Tools

### 1. list_chores

List all chores with optional filtering.

**Parameters**:
- `filter_active` (boolean, optional): Filter by active status
- `assigned_to_user_id` (integer, optional): Filter by assigned user ID

**Example**:
```
List all active chores assigned to me
```

### 2. get_chore

Get details of a specific chore by ID.

**Parameters**:
- `chore_id` (integer, required): The chore ID

**Example**:
```
Show me details of chore 123
```

### 3. create_chore

Create a new chore with full configuration support.

**Basic Parameters**:
- `name` (string, required): Chore name (1-200 characters)
- `description` (string, optional): Chore description (max 5000 characters)
- `due_date` (string, optional): Due date in YYYY-MM-DD or RFC3339 format
- `created_by` (integer, optional): Creator user ID

**Recurrence/Frequency Parameters**:
- `frequency_type` (string, optional): How often chore repeats - "once", "daily", "weekly", "monthly", "yearly", "interval_based" (default: "once")
- `frequency` (integer, optional): Frequency multiplier, e.g., 1=weekly, 2=biweekly (default: 1)
- `frequency_metadata` (object, optional): Additional frequency config like `{"days": [1,3,5], "time": "09:00"}`
- `is_rolling` (boolean, optional): Rolling schedule (next due based on completion) vs fixed (default: false)

**User Assignment Parameters**:
- `assigned_to` (integer, optional): Primary assigned user ID
- `assignees` (array, optional): Multiple assignees as `[{"userId": 1}, {"userId": 2}]`
- `assign_strategy` (string, optional): Assignment strategy - "least_completed", "round_robin", "random" (default: "least_completed")

**Notification Parameters**:
- `notification` (boolean, optional): Enable notifications (default: false)
- `nagging` (boolean, optional): Enable nagging/reminder notifications (default: false)
- `predue` (boolean, optional): Enable pre-due date notifications (default: false)

**Organization Parameters**:
- `priority` (integer, optional): Priority level 1-5 (1=lowest, 5=highest)
- `labels` (array, optional): Label tags like `["cleaning", "outdoor"]`

**Status Parameters**:
- `is_active` (boolean, optional): Active status - inactive chores are hidden (default: true)
- `is_private` (boolean, optional): Private chore visible only to creator (default: false)

**Gamification Parameters**:
- `points` (integer, optional): Points awarded for completion

**Advanced Parameters**:
- `sub_tasks` (array, optional): Sub-tasks/checklist items

**Examples**:
```
Create a simple one-time chore:
Create a chore called "Take out trash" due on 2025-11-10

Create a recurring chore with notifications:
Create a weekly chore "Clean kitchen" every Monday at 9am with priority 4,
enable nagging notifications, and assign it to user 1

Create an advanced chore:
Create a chore "Grocery shopping" that repeats weekly on Mondays and Wednesdays,
assign to users 1 and 2 using round robin strategy, with priority 3,
labels "shopping" and "outdoor", and award 10 points
```

### 4. complete_chore

Mark a chore as complete. **Requires Donetick Plus/Premium**.

**Parameters**:
- `chore_id` (integer, required): The chore ID
- `completed_by` (integer, optional): User ID who completed it

**Example**:
```
Mark chore 123 as complete
```

### 5. delete_chore

Delete a chore permanently. **Only the creator can delete**.

**Parameters**:
- `chore_id` (integer, required): The chore ID

**Example**:
```
Delete chore 123
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DONETICK_BASE_URL` | Yes | - | Your Donetick instance URL |
| `DONETICK_API_TOKEN` | Yes | - | API token from Donetick |
| `LOG_LEVEL` | No | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `RATE_LIMIT_PER_SECOND` | No | 10.0 | Requests per second limit |
| `RATE_LIMIT_BURST` | No | 10 | Maximum burst size |

### Rate Limiting

The server implements a token bucket rate limiter to prevent API overload:

- **Default**: 10 requests per second with burst capacity of 10
- **Conservative**: Starts conservative and can be increased based on your Donetick instance
- **Respects 429**: Automatically backs off when rate limited by the API

### Retry Logic

- **Exponential backoff** with jitter for transient failures
- **Maximum 3 retries** for most operations
- **Smart retry**: Only retries on 5xx errors and 429 (rate limit)
- **No retry on 4xx**: Client errors fail immediately (except 429)

## Development

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=donetick_mcp --cov-report=html

# Run specific test file
pytest tests/test_client.py

# Run with verbose output
pytest -v
```

### Project Structure

```
donetick-mcp-server/
├── src/donetick_mcp/
│   ├── __init__.py
│   ├── server.py          # MCP server implementation
│   ├── client.py           # Donetick API client
│   ├── models.py           # Pydantic data models
│   └── config.py           # Configuration management
├── tests/
│   ├── test_client.py      # API client tests
│   └── test_server.py      # MCP server tests
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

## API Documentation

This server uses the Donetick external API (eAPI). Official documentation:
- **API Docs**: https://docs.donetick.com/advance-settings/api/
- **GitHub**: https://github.com/donetick/donetick

### Important Notes

1. **Authentication**: Uses `secretkey` header (not standard Bearer token)
2. **Premium Features**: Complete and update operations require Donetick Plus
3. **No GET by ID**: The API doesn't have GET /chore/:id, so we fetch all and filter
4. **Circle Scoped**: All operations are scoped to your circle (household/team)

## Troubleshooting

### Common Issues

**"DONETICK_BASE_URL environment variable is required"**
- Make sure your `.env` file exists and is properly formatted
- For Docker: ensure environment variables are passed in docker-compose.yml

**"Rate limited, waiting..."**
- The server is respecting API rate limits
- Consider reducing `RATE_LIMIT_PER_SECOND` if this happens frequently

**"Connection refused" or timeout errors**
- Verify your Donetick instance URL is correct
- Check that your Donetick instance is accessible
- Ensure firewall rules allow outbound connections

**"401 Unauthorized"**
- Verify your API token is correct
- Check that the token hasn't been revoked
- Generate a new token from Donetick settings if needed

**Tools not showing in Claude**
- Restart Claude Desktop after configuration changes
- Check Claude Desktop logs for errors
- Verify the configuration file path is correct

### Debugging

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
```

Or in Docker:

```yaml
environment:
  - LOG_LEVEL=DEBUG
```

View Docker logs:

```bash
docker-compose logs -f donetick-mcp
```

## Security

- **API Token**: Never commit tokens to version control
- **Docker Isolation**: Runs as non-root user in container
- **Resource Limits**: Memory and CPU limits prevent resource exhaustion
- **Input Validation**: Pydantic models validate all inputs
- **HTTPS**: Always use HTTPS for Donetick instance URLs

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- [Donetick](https://donetick.com) - Open source chores management
- [Model Context Protocol](https://modelcontextprotocol.io) - MCP specification
- [Anthropic](https://anthropic.com) - MCP SDK and Claude

## Support

- **Issues**: https://github.com/jason1365/donetick-mcp-server/issues
- **Donetick Docs**: https://docs.donetick.com
- **MCP Docs**: https://modelcontextprotocol.io

---

Built with ❤️ for the Donetick and MCP communities
