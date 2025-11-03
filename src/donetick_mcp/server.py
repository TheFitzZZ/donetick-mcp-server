"""Donetick MCP server implementation."""

import asyncio
import json
import logging
import urllib.parse
from typing import Any, Optional

import httpx
from mcp.server import Server
from mcp.types import TextContent, Tool

from .client import DonetickClient
from .config import config
from .models import ChoreCreate

# Configure logging
config.configure_logging()
logger = logging.getLogger(__name__)

# Initialize MCP server
app = Server("donetick-chores")

# Global client instance (initialized on startup)
client: Optional[DonetickClient] = None


async def get_client() -> DonetickClient:
    """Get or create the global Donetick client."""
    global client
    if client is None:
        client = DonetickClient()
    return client


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List all available MCP tools."""
    return [
        Tool(
            name="list_chores",
            description=(
                "List all chores from Donetick. "
                "Optionally filter by active status or assigned user. "
                "Returns comprehensive chore details including name, description, "
                "due dates, assignees, and status."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "filter_active": {
                        "type": "boolean",
                        "description": "Filter by active status (true=active only, false=inactive only, null=all)",
                    },
                    "assigned_to_user_id": {
                        "type": "integer",
                        "description": "Filter by assigned user ID (null=all users)",
                    },
                },
            },
        ),
        Tool(
            name="get_chore",
            description=(
                "Get details of a specific chore by its ID. "
                "Returns complete chore information including all metadata, "
                "assignees, labels, and scheduling details."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "chore_id": {
                        "type": "integer",
                        "description": "The ID of the chore to retrieve",
                    },
                },
                "required": ["chore_id"],
            },
        ),
        Tool(
            name="create_chore",
            description=(
                "Create a new chore in Donetick with full configuration support. "
                "Supports recurrence/frequency, user assignment, notifications, "
                "labels, priority, points, sub-tasks, and more. "
                "Returns the created chore with its assigned ID and metadata."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    # Basic Information
                    "name": {
                        "type": "string",
                        "description": "Chore name (required, 1-200 characters)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Chore description (optional, max 5000 characters)",
                    },
                    "due_date": {
                        "type": "string",
                        "description": "Due date in YYYY-MM-DD or RFC3339 format (optional)",
                    },
                    "created_by": {
                        "type": "integer",
                        "description": "User ID of the creator (optional)",
                    },

                    # Recurrence/Frequency
                    "frequency_type": {
                        "type": "string",
                        "enum": ["once", "daily", "weekly", "monthly", "yearly", "interval_based"],
                        "description": "How often the chore repeats (default: once)",
                    },
                    "frequency": {
                        "type": "integer",
                        "description": "Frequency multiplier (e.g., 1=weekly, 2=biweekly, default: 1)",
                        "minimum": 1,
                    },
                    "frequency_metadata": {
                        "type": "object",
                        "description": "Additional frequency config (e.g., {\"days\": [1,3,5], \"time\": \"09:00\"})",
                    },
                    "is_rolling": {
                        "type": "boolean",
                        "description": "Rolling schedule (next due based on completion) vs fixed (default: false)",
                    },

                    # User Assignment
                    "assigned_to": {
                        "type": "integer",
                        "description": "Primary assigned user ID (optional)",
                    },
                    "assignees": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Multiple assignees as array of {\"userId\": int} objects",
                    },
                    "assign_strategy": {
                        "type": "string",
                        "enum": ["least_completed", "round_robin", "random"],
                        "description": "Assignment strategy (default: least_completed)",
                    },

                    # Notifications
                    "notification": {
                        "type": "boolean",
                        "description": "Enable notifications for this chore (default: false)",
                    },
                    "nagging": {
                        "type": "boolean",
                        "description": "Enable nagging/reminder notifications (default: false)",
                    },
                    "predue": {
                        "type": "boolean",
                        "description": "Enable pre-due date notifications (default: false)",
                    },

                    # Organization
                    "priority": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 5,
                        "description": "Priority level: 1=lowest, 5=highest (optional)",
                    },
                    "labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Label tags for categorization (e.g., [\"cleaning\", \"outdoor\"])",
                    },

                    # Status
                    "is_active": {
                        "type": "boolean",
                        "description": "Active status - inactive chores are hidden (default: true)",
                    },
                    "is_private": {
                        "type": "boolean",
                        "description": "Private chore visible only to creator (default: false)",
                    },

                    # Gamification
                    "points": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Points awarded for completion (optional)",
                    },

                    # Advanced
                    "sub_tasks": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Sub-tasks/checklist items (optional)",
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="complete_chore",
            description=(
                "Mark a chore as complete. "
                "This is a Donetick Plus/Premium feature. "
                "Optionally specify which user completed the chore. "
                "Returns the updated chore with completion timestamp."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "chore_id": {
                        "type": "integer",
                        "description": "The ID of the chore to mark complete",
                    },
                    "completed_by": {
                        "type": "integer",
                        "description": "User ID who completed the chore (optional)",
                    },
                },
                "required": ["chore_id"],
            },
        ),
        Tool(
            name="delete_chore",
            description=(
                "Delete a chore permanently. "
                "Note: Only the chore creator can delete a chore. "
                "Returns confirmation of deletion."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "chore_id": {
                        "type": "integer",
                        "description": "The ID of the chore to delete",
                    },
                },
                "required": ["chore_id"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool execution."""
    try:
        client = await get_client()

        if name == "list_chores":
            filter_active = arguments.get("filter_active")
            assigned_to_user_id = arguments.get("assigned_to_user_id")

            chores = await client.list_chores(
                filter_active=filter_active,
                assigned_to_user_id=assigned_to_user_id,
            )

            # Format response
            if not chores:
                return [TextContent(type="text", text="No chores found.")]

            result = {
                "count": len(chores),
                "chores": [chore.model_dump() for chore in chores],
            }

            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_chore":
            chore_id = arguments["chore_id"]
            chore = await client.get_chore(chore_id)

            if not chore:
                return [
                    TextContent(
                        type="text",
                        text=f"Chore with ID {chore_id} not found.",
                    )
                ]

            return [TextContent(type="text", text=json.dumps(chore.model_dump(), indent=2))]

        elif name == "create_chore":
            # Build notification metadata
            notification_metadata = {
                "nagging": arguments.get("nagging", False),
                "predue": arguments.get("predue", False),
            }

            # Build chore create request with all parameters
            chore_create = ChoreCreate(
                # Basic Information
                Name=arguments["name"],
                Description=arguments.get("description"),
                DueDate=arguments.get("due_date"),
                CreatedBy=arguments.get("created_by"),

                # Recurrence/Frequency
                FrequencyType=arguments.get("frequency_type", "once"),
                Frequency=arguments.get("frequency", 1),
                FrequencyMetadata=arguments.get("frequency_metadata", {}),
                IsRolling=arguments.get("is_rolling", False),

                # User Assignment
                AssignedTo=arguments.get("assigned_to"),
                Assignees=arguments.get("assignees", []),
                AssignStrategy=arguments.get("assign_strategy", "least_completed"),

                # Notifications
                Notification=arguments.get("notification", False),
                NotificationMetadata=notification_metadata,

                # Organization & Priority
                Priority=arguments.get("priority"),
                Labels=arguments.get("labels", []),
                LabelsV2=arguments.get("labels_v2", []),

                # Status & Visibility
                IsActive=arguments.get("is_active", True),
                IsPrivate=arguments.get("is_private", False),

                # Gamification
                Points=arguments.get("points"),

                # Advanced Features
                SubTasks=arguments.get("sub_tasks", []),
                ThingChore=arguments.get("thing_chore"),
            )

            chore = await client.create_chore(chore_create)

            return [
                TextContent(
                    type="text",
                    text=f"Successfully created chore '{chore.name}' (ID: {chore.id})\n\n{json.dumps(chore.model_dump(), indent=2)}",
                )
            ]

        elif name == "complete_chore":
            chore_id = arguments["chore_id"]
            completed_by = arguments.get("completed_by")

            chore = await client.complete_chore(chore_id, completed_by=completed_by)

            return [
                TextContent(
                    type="text",
                    text=f"Successfully completed chore '{chore.name}' (ID: {chore.id})\n\n"
                    + json.dumps(chore.model_dump(), indent=2),
                )
            ]

        elif name == "delete_chore":
            chore_id = arguments["chore_id"]

            await client.delete_chore(chore_id)

            return [
                TextContent(
                    type="text",
                    text=f"Successfully deleted chore with ID {chore_id}.",
                )
            ]

        else:
            return [
                TextContent(
                    type="text",
                    text=f"Unknown tool: {name}",
                )
            ]

    except httpx.HTTPStatusError as e:
        # Log full error internally
        logger.error(f"HTTP error executing tool {name}: {e.response.status_code} - {e.response.text}", exc_info=True)

        # Return sanitized error to user
        status_code = e.response.status_code
        if status_code == 401:
            error_msg = "Authentication failed. Please check your API token."
        elif status_code == 403:
            error_msg = "Permission denied. This operation may require Donetick Plus membership."
        elif status_code == 404:
            error_msg = "Resource not found."
        elif status_code == 429:
            error_msg = "Rate limit exceeded. Please try again later."
        elif 400 <= status_code < 500:
            error_msg = f"Request failed with status {status_code}. Please check your input."
        else:
            error_msg = f"API request failed with status {status_code}."

        return [TextContent(type="text", text=f"Error: {error_msg}")]

    except httpx.TimeoutException as e:
        logger.error(f"Timeout executing tool {name}: {e}", exc_info=True)
        return [TextContent(type="text", text="Error: Request timed out. Please try again.")]

    except ValueError as e:
        # Validation errors (safe to expose)
        logger.warning(f"Validation error in tool {name}: {e}")
        return [TextContent(type="text", text=f"Validation Error: {str(e)}")]

    except Exception as e:
        # Log full error internally
        logger.error(f"Unexpected error executing tool {name}: {e}", exc_info=True)

        # Return generic error to user (don't leak internals)
        return [TextContent(type="text", text="Error: An unexpected error occurred while processing your request.")]


async def cleanup():
    """Cleanup resources on shutdown."""
    global client
    if client:
        try:
            await client.close()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)
        finally:
            client = None


def sanitize_url(url: str) -> str:
    """Sanitize URL for logging by removing sensitive parts."""
    try:
        parsed = urllib.parse.urlparse(url)
        # Only show scheme and path, hide host details
        return f"{parsed.scheme}://[SERVER]{parsed.path}"
    except Exception:
        return "[URL]"


def main():
    """Main entry point for the MCP server."""
    import sys

    try:
        # Run the MCP server with stdio transport
        import mcp.server.stdio

        logger.info("Starting Donetick MCP server...")
        logger.info(f"Connecting to: {sanitize_url(config.donetick_base_url)}")

        # Run with stdio transport
        mcp.server.stdio.stdio_server()(app)

    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Cleanup with proper async handling
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(cleanup())
            elif not loop.is_closed():
                loop.run_until_complete(cleanup())
            else:
                # Create new loop for cleanup
                asyncio.run(cleanup())
        except Exception as e:
            logger.error(f"Cleanup error: {e}", exc_info=True)


if __name__ == "__main__":
    main()
