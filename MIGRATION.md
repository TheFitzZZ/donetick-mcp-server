# Migration Guide: v1.x to v2.0.0

This guide helps you migrate from Donetick MCP Server v1.x to v2.0.0. The new version includes breaking changes that improve reliability and feature coverage.

## Overview

Version 2.0.0 introduces a fundamental change in how authentication works with the Donetick API, switching from the external API (eAPI) to the full API with JWT-based authentication. This change unlocks previously unavailable features and provides a more stable integration.

## Breaking Changes

### 1. Authentication Method Changed

**v1.x**: Used API tokens with `secretkey` header
```python
headers = {"secretkey": api_token}
```

**v2.0.0**: Uses JWT authentication with username/password
```python
# Automatic JWT token management
# Login once, token automatically refreshed
```

### 2. API Endpoints Changed

**v1.x**: Used external API (eAPI) endpoints
- `GET /eapi/v1/chore`
- `POST /eapi/v1/chore`
- `POST /eapi/v1/chore/:id/complete`
- `DELETE /eapi/v1/chore/:id`

**v2.0.0**: Uses full API endpoints
- `GET /api/chores`
- `POST /api/chores`
- `PUT /api/chores/:id/do`
- `DELETE /api/chores/:id`
- Plus many more available endpoints

### 3. Features Now Working

The following 9 features were NOT working in v1.x but ARE working in v2.0.0:

1. **Frequency Metadata** (`frequency_metadata`) - Configure specific days, times for recurring chores
2. **Rolling Schedules** (`is_rolling`) - Next due date based on completion vs fixed schedule
3. **Multiple Assignees** (`assignees`) - Assign chores to multiple users
4. **Assignment Strategy** (`assign_strategy`) - Control how chores rotate among assignees
5. **Nagging Notifications** (`nagging`) - Send reminder notifications
6. **Pre-due Notifications** (`predue`) - Notify before due date
7. **Private Chores** (`is_private`) - Hide chores from other circle members
8. **Points/Gamification** (`points`) - Award points for chore completion
9. **Sub-tasks** (`sub_tasks`) - Add checklist items to chores

### 4. Premium Features No Longer Required

In v1.x, these operations required Donetick Plus membership:
- `complete_chore`
- `update_chore`
- `get_circle_members`

In v2.0.0, these operations work with standard Donetick accounts using the full API.

## Environment Variable Changes

### Old Configuration (v1.x)

```env
# .env file for v1.x
DONETICK_BASE_URL=https://your-instance.com
DONETICK_API_TOKEN=dt_1234567890abcdef  # API token from settings
LOG_LEVEL=INFO
```

### New Configuration (v2.0.0)

```env
# .env file for v2.0.0
DONETICK_BASE_URL=https://your-instance.com
DONETICK_USERNAME=your_username  # Your Donetick username
DONETICK_PASSWORD=your_password  # Your Donetick password
LOG_LEVEL=INFO
```

### Configuration Changes Summary

| Variable | v1.x | v2.0.0 | Status |
|----------|------|--------|--------|
| `DONETICK_BASE_URL` | Required | Required | Unchanged |
| `DONETICK_API_TOKEN` | Required | Removed | **BREAKING** |
| `DONETICK_USERNAME` | N/A | Required | **NEW** |
| `DONETICK_PASSWORD` | N/A | Required | **NEW** |
| `LOG_LEVEL` | Optional | Optional | Unchanged |
| `RATE_LIMIT_PER_SECOND` | Optional | Optional | Unchanged |
| `RATE_LIMIT_BURST` | Optional | Optional | Unchanged |

## Step-by-Step Migration

### Step 1: Obtain Your Credentials

You need your Donetick username and password. This is the same login you use to access the Donetick web interface.

**Important Security Notes**:
- Store credentials securely in your `.env` file
- Never commit `.env` file to version control
- Consider using environment-specific credentials for different deployments
- The server stores JWT tokens in memory only (not persisted to disk)

### Step 2: Update Environment Variables

#### Docker Deployment

1. Edit your `.env` file:
```bash
cd donetick-mcp-server
nano .env  # or use your preferred editor
```

2. Replace the configuration:
```env
# Remove this line:
# DONETICK_API_TOKEN=dt_1234567890abcdef

# Add these lines:
DONETICK_USERNAME=your_username
DONETICK_PASSWORD=your_password
```

3. Rebuild and restart the container:
```bash
docker-compose down
docker-compose build
docker-compose up -d
```

#### Python Virtual Environment

1. Update environment variables:
```bash
# Remove old variable
unset DONETICK_API_TOKEN

# Set new variables
export DONETICK_USERNAME=your_username
export DONETICK_PASSWORD=your_password
```

2. Or update your `.env` file if using python-dotenv:
```bash
cd donetick-mcp-server
nano .env
```

3. Restart the server:
```bash
python -m donetick_mcp.server
```

#### Claude Desktop Configuration

Update your Claude Desktop config file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**Linux**: `~/.config/Claude/claude_desktop_config.json`

**Before (v1.x)**:
```json
{
  "mcpServers": {
    "donetick": {
      "command": "python",
      "args": ["-m", "donetick_mcp.server"],
      "env": {
        "DONETICK_BASE_URL": "https://your-instance.com",
        "DONETICK_API_TOKEN": "your_api_token_here"
      }
    }
  }
}
```

**After (v2.0.0)**:
```json
{
  "mcpServers": {
    "donetick": {
      "command": "python",
      "args": ["-m", "donetick_mcp.server"],
      "env": {
        "DONETICK_BASE_URL": "https://your-instance.com",
        "DONETICK_USERNAME": "your_username",
        "DONETICK_PASSWORD": "your_password"
      }
    }
  }
}
```

**Restart Claude Desktop** after making changes.

### Step 3: Test New Authentication

#### Test with Docker

```bash
# View logs to verify authentication
docker-compose logs -f donetick-mcp

# Look for successful login message
# Expected: "Successfully authenticated with Donetick API"
```

#### Test with Python

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run the server
python -m donetick_mcp.server

# You should see JWT token acquisition in logs
```

#### Test in Claude Desktop

1. Open Claude Desktop
2. Start a new conversation
3. Try a simple command:
   ```
   List my active chores
   ```

4. If authentication works, you'll see your chores
5. If authentication fails, check the logs for error messages

### Step 4: Verify Features Work

Test the 9 previously non-functional features:

```
Create a weekly chore "Clean kitchen" that repeats every Monday and Wednesday
at 9am, with rolling schedule, assign to users 1 and 2 using round robin,
enable nagging notifications, mark as private, and award 10 points
```

This command tests:
- Frequency metadata (specific days and time)
- Rolling schedule
- Multiple assignees
- Assignment strategy (round robin)
- Nagging notifications
- Private chores
- Points/gamification

### Step 5: Update Your Workflows

If you have scripts or automation that interact with the MCP server:

1. **Update environment variable names** in all scripts
2. **Remove API token generation** from setup scripts
3. **Update documentation** for your team
4. **Test all automated workflows** with new authentication

## JWT Token Management

### How JWT Tokens Work in v2.0.0

1. **Initial Login**: Server logs in with username/password on startup
2. **Token Storage**: JWT token stored in memory (not persisted)
3. **Automatic Refresh**: Token refreshed automatically before expiration
4. **Session Management**: Each server instance maintains its own session
5. **Security**: Tokens never logged or written to disk

### Token Lifecycle

```
Server Start → Login Request → JWT Token Received → Store in Memory
                                        ↓
                        Token expires in ~24h → Auto-refresh → Continue
                                        ↓
                        Server Restart → Re-login Required
```

### Token Expiration Handling

The server automatically handles token expiration:

- **Proactive Refresh**: Tokens refreshed before expiration
- **Error Recovery**: If refresh fails, re-authenticates automatically
- **No User Action**: Token management is completely transparent
- **Logging**: Token refresh logged at DEBUG level

## Troubleshooting

### Error: "DONETICK_API_TOKEN environment variable is required"

**Cause**: Running v2.0.0 with v1.x configuration

**Solution**: Update environment variables to use `DONETICK_USERNAME` and `DONETICK_PASSWORD`

### Error: "401 Unauthorized" or "Invalid credentials"

**Causes**:
- Incorrect username or password
- Account locked or disabled
- Donetick instance not accessible

**Solutions**:
1. Verify credentials by logging into Donetick web interface
2. Check username/password for typos
3. Ensure Donetick instance URL is correct
4. Check that account is not locked

### Error: "JWT token expired"

**Cause**: Token expired and automatic refresh failed

**Solutions**:
1. Check logs for refresh errors: `docker-compose logs -f donetick-mcp`
2. Restart server to force re-authentication: `docker-compose restart`
3. Verify credentials are still valid
4. Check network connectivity to Donetick instance

### Features Still Not Working

**Symptoms**: Commands using frequency_metadata, assignees, etc. fail

**Causes**:
- Still running v1.x code
- Configuration not updated
- Cached old version

**Solutions**:
1. Verify version: Check logs for "v2.0.0" in startup message
2. Rebuild container: `docker-compose build --no-cache`
3. Clear Python cache: `find . -type d -name __pycache__ -exec rm -r {} +`
4. Reinstall: `pip install -e . --force-reinstall`

### Claude Desktop Not Recognizing Changes

**Symptoms**: Tools still using old authentication

**Solutions**:
1. Fully restart Claude Desktop (don't just reload)
2. Check config file path is correct
3. Verify JSON syntax is valid
4. Check Claude Desktop logs for errors

## Rollback Instructions

If you need to rollback to v1.x:

### Step 1: Checkout v1.x Code

```bash
cd donetick-mcp-server
git fetch --all --tags
git checkout v1.2.0  # or your preferred v1.x version
```

### Step 2: Restore v1.x Configuration

1. Edit `.env` file:
```env
# Remove v2.0.0 variables:
# DONETICK_USERNAME=...
# DONETICK_PASSWORD=...

# Add v1.x variable:
DONETICK_API_TOKEN=your_api_token_here
```

2. Generate new API token if needed:
   - Login to Donetick
   - Settings → Advanced Settings → Access Token
   - Generate new token

### Step 3: Rebuild/Restart

#### Docker
```bash
docker-compose down
docker-compose build
docker-compose up -d
```

#### Python
```bash
pip install -e . --force-reinstall
python -m donetick_mcp.server
```

### Step 4: Update Claude Desktop Config

Restore v1.x configuration in `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "donetick": {
      "command": "python",
      "args": ["-m", "donetick_mcp.server"],
      "env": {
        "DONETICK_BASE_URL": "https://your-instance.com",
        "DONETICK_API_TOKEN": "your_api_token_here"
      }
    }
  }
}
```

Restart Claude Desktop.

### Step 5: Verify Rollback

```bash
# Check version in logs
docker-compose logs donetick-mcp | grep version

# Test basic functionality
# In Claude: "List my chores"
```

## Need Help?

- **Issues**: https://github.com/jason1365/donetick-mcp-server/issues
- **Discussions**: https://github.com/jason1365/donetick-mcp-server/discussions
- **Donetick Docs**: https://docs.donetick.com

## Summary

v2.0.0 brings significant improvements but requires environment variable changes:

**Key Changes**:
1. Replace `DONETICK_API_TOKEN` with `DONETICK_USERNAME` and `DONETICK_PASSWORD`
2. 9 previously broken features now work
3. No Premium membership required for advanced features
4. JWT tokens managed automatically

**Migration Time**: 5-10 minutes for most deployments

**Benefits**:
- Full feature support (26+ chore creation fields)
- More reliable authentication
- No Premium membership required
- Better error handling
- Automatic token refresh

Welcome to v2.0.0!
