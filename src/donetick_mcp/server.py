"""Donetick MCP server implementation."""

import asyncio
import json
import logging
import urllib.parse
from typing import Any, Optional

import httpx
from mcp.server import Server
from mcp.types import TextContent, Tool

from . import __version__
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
        Tool(
            name="list_labels",
            description=(
                "List all labels in the circle. "
                "Returns all available labels with their IDs, names, and colors. "
                "Use these labels to organize and categorize chores."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="create_label",
            description=(
                "Create a new label for organizing chores. "
                "Labels help categorize and filter chores by type, location, or any custom criteria. "
                "Optionally specify a color in hex format (e.g., '#FF5733')."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Label name (required)",
                    },
                    "color": {
                        "type": "string",
                        "description": "Label color in hex format (e.g., '#80d8ff'), optional",
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="update_label",
            description=(
                "Update an existing label's name and/or color. "
                "Use this to rename labels or change their colors for better organization."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "label_id": {
                        "type": "integer",
                        "description": "The ID of the label to update",
                    },
                    "name": {
                        "type": "string",
                        "description": "New label name",
                    },
                    "color": {
                        "type": "string",
                        "description": "New label color in hex format (e.g., '#80d8ff'), optional",
                    },
                },
                "required": ["label_id", "name"],
            },
        ),
        Tool(
            name="delete_label",
            description=(
                "Delete a label permanently. "
                "This will remove the label from all chores that use it. "
                "Use with caution as this action cannot be undone."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "label_id": {
                        "type": "integer",
                        "description": "The ID of the label to delete",
                    },
                },
                "required": ["label_id"],
            },
        ),
        Tool(
            name="get_circle_members",
            description=(
                "Get all members in the circle (household/team). "
                "Returns user information including user IDs, usernames, display names, "
                "roles (admin/member), active status, and points. "
                "Use this to see who you can assign chores to."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
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

        elif name == "list_labels":
            labels = await client.get_labels()

            # Format labels for display
            labels_text = "Available Labels:\n\n"
            for label in labels:
                color_info = f" (Color: {label.color})" if label.color else ""
                labels_text += f"- ID {label.id}: {label.name}{color_info}\n"

            if not labels:
                labels_text = "No labels found in this circle."

            return [
                TextContent(
                    type="text",
                    text=labels_text,
                )
            ]

        elif name == "create_label":
            name_arg = arguments["name"]
            color = arguments.get("color")

            label = await client.create_label(name=name_arg, color=color)

            color_info = f" with color {label.color}" if label.color else ""
            return [
                TextContent(
                    type="text",
                    text=f"Successfully created label '{label.name}' (ID: {label.id}){color_info}.",
                )
            ]

        elif name == "update_label":
            label_id = arguments["label_id"]
            name_arg = arguments["name"]
            color = arguments.get("color")

            label = await client.update_label(label_id=label_id, name=name_arg, color=color)

            color_info = f" with color {label.color}" if label.color else ""
            return [
                TextContent(
                    type="text",
                    text=f"Successfully updated label ID {label.id} to '{label.name}'{color_info}.",
                )
            ]

        elif name == "delete_label":
            label_id = arguments["label_id"]

            await client.delete_label(label_id)

            return [
                TextContent(
                    type="text",
                    text=f"Successfully deleted label with ID {label_id}.",
                )
            ]

        elif name == "get_circle_members":
            members = await client.get_circle_members()

            # Format member information
            member_list = []
            for member in members:
                role_emoji = "👑" if member.role == "admin" else "👤"
                status_emoji = "✅" if member.isActive else "❌"
                display_name = member.displayName or "(no display name)"

                member_info = (
                    f"{role_emoji} {status_emoji} {member.username}\n"
                    f"  User ID: {member.userId}\n"
                    f"  Display Name: {display_name}\n"
                    f"  Role: {member.role}\n"
                    f"  Points: {member.points} (Redeemed: {member.pointsRedeemed})"
                )
                member_list.append(member_info)

            result_text = (
                f"Found {len(members)} member(s) in your circle:\n\n" +
                "\n\n".join(member_list)
            )

            return [
                TextContent(
                    type="text",
                    text=result_text,
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
            error_msg = "Authentication failed. Please check your username and password."
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


async def main_async():
    """Async main entry point for the MCP server."""
    import sys
    from mcp.server.stdio import stdio_server

    logger.info(f"Starting Donetick MCP Server v{__version__}")
    logger.info(f"Connecting to: {sanitize_url(config.donetick_base_url)}")
    logger.info(f"Username: {config.donetick_username}")

    # Print to stderr for visibility in Claude Desktop
    print(f"Donetick MCP Server v{__version__} starting...", file=sys.stderr)

    # Run with stdio transport - this blocks until the server stops
    logger.info("Initializing stdio transport...")
    async with stdio_server() as (read_stream, write_stream):
        logger.info("Server running and ready to accept requests")
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


def main():
    """Main entry point for the MCP server."""
    import sys
    import traceback

    try:
        # Run the async main function
        asyncio.run(main_async())

    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        # Log to both logger and stderr to ensure visibility in Claude Desktop logs
        error_msg = f"Server error: {e}\n{traceback.format_exc()}"
        logger.error(error_msg)
        print(error_msg, file=sys.stderr)
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
            cleanup_error = f"Cleanup error: {e}\n{traceback.format_exc()}"
            logger.error(cleanup_error)
            print(cleanup_error, file=sys.stderr)


if __name__ == "__main__":
    import sys
    import traceback

    try:
        main()
    except Exception as e:
        # Catch any errors during initialization (e.g., config validation)
        error_msg = f"Failed to start server: {e}\n{traceback.format_exc()}"
        print(error_msg, file=sys.stderr)
        sys.exit(1)
