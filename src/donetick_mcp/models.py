"""Pydantic models for Donetick API requests and responses."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Assignee(BaseModel):
    """Chore assignee model."""

    userId: int = Field(..., description="User ID of the assignee")


class Label(BaseModel):
    """Chore label model."""

    id: int = Field(..., description="Label ID")
    name: str = Field(..., description="Label name")
    color: Optional[str] = Field(None, description="Label color (hex code)")
    created_by: Optional[int] = Field(None, alias="createdBy", description="User ID who created the label")


class NotificationMetadata(BaseModel):
    """Notification configuration metadata."""

    nagging: bool = Field(default=False, description="Enable nagging notifications")
    predue: bool = Field(default=False, description="Enable pre-due notifications")


class ChoreCreate(BaseModel):
    """Enhanced model for creating a new chore with full feature support."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "name": "Take out the trash",
                "description": "Weekly trash collection on Monday mornings",
                "dueDate": "2025-11-10T09:00:00Z",
                "createdBy": 1,
                "frequencyType": "weekly",
                "frequency": 1,
                "frequencyMetadata": {"days": [1], "time": "09:00"},
                "isRolling": False,
                "assignedTo": 1,
                "assignees": [{"userId": 1}, {"userId": 2}],
                "assignStrategy": "least_completed",
                "notification": True,
                "notificationMetadata": {"nagging": True, "predue": True},
                "priority": 3,
                "labels": ["cleaning", "outdoor"],
                "isActive": True,
                "isPrivate": False,
                "points": 10,
                "completionWindow": 7,
                "requireApproval": False,
                "deadlineOffset": 0,
            }
        }
    )

    # Basic Information
    name: str = Field(
        ...,
        alias="Name",
        min_length=1,
        max_length=200,
        description="Chore name (required)"
    )
    description: Optional[str] = Field(
        None,
        alias="Description",
        max_length=5000,
        description="Chore description"
    )
    dueDate: Optional[str] = Field(
        None,
        alias="DueDate",
        description="Due date in RFC3339 or YYYY-MM-DD format",
    )
    createdBy: Optional[int] = Field(
        None,
        alias="CreatedBy",
        description="User ID of creator"
    )

    # Recurrence/Frequency Settings
    frequencyType: Optional[str] = Field(
        default="once",
        alias="FrequencyType",
        description="Frequency type: once, daily, weekly, monthly, yearly, interval_based",
    )
    frequency: Optional[int] = Field(
        default=1,
        alias="Frequency",
        ge=0,
        description="Frequency value (e.g., 0=once, 1=weekly, 2=biweekly)",
    )
    frequencyMetadata: Optional[dict[str, Any]] = Field(
        default_factory=dict,
        alias="FrequencyMetadata",
        description="Additional frequency configuration (e.g., days of week, time)",
    )
    isRolling: Optional[bool] = Field(
        default=False,
        alias="IsRolling",
        description="Rolling schedule (next due date based on completion) vs fixed schedule",
    )

    # User Assignment
    assignedTo: Optional[int] = Field(
        None,
        alias="AssignedTo",
        description="Primary assigned user ID"
    )
    assignees: Optional[list[dict[str, int]]] = Field(
        default_factory=list,
        alias="Assignees",
        description="List of assignee objects with userId field",
    )
    assignStrategy: Optional[str] = Field(
        default="least_completed",
        alias="AssignStrategy",
        description="Assignment strategy: least_completed, round_robin, random",
    )

    # Notifications
    notification: Optional[bool] = Field(
        default=False,
        alias="Notification",
        description="Enable notifications for this chore"
    )
    notificationMetadata: Optional[dict[str, Any]] = Field(
        default=None,
        alias="NotificationMetadata",
        description="Notification settings with templates array: [{value: int, unit: str}]",
    )

    # Organization & Priority
    priority: Optional[int] = Field(
        None,
        alias="Priority",
        ge=0,
        le=4,
        description="Priority level (0=unset, 1=lowest, 4=highest)"
    )
    labels: Optional[list[str]] = Field(
        default_factory=list,
        alias="Labels",
        description="Label tags for categorization (legacy - use labelsV2)"
    )
    labelsV2: Optional[list[dict[str, int]]] = Field(
        default_factory=list,
        alias="LabelsV2",
        description="Label references - list of objects with 'id' field: [{'id': 1}, {'id': 2}]",
    )

    # Status & Visibility
    isActive: Optional[bool] = Field(
        default=True,
        alias="IsActive",
        description="Active status (inactive chores are hidden)"
    )
    isPrivate: Optional[bool] = Field(
        default=False,
        alias="IsPrivate",
        description="Private chore (visible only to creator)"
    )

    # Gamification
    points: Optional[int] = Field(
        None,
        alias="Points",
        ge=0,
        description="Points awarded for completion"
    )

    # Advanced Features
    subTasks: Optional[list[dict[str, Any]]] = Field(
        default_factory=list,
        alias="SubTasks",
        description="Sub-tasks/checklist items"
    )
    thingChore: Optional[dict[str, Any]] = Field(
        None,
        alias="ThingChore",
        description="Thing/device association metadata"
    )

    # Completion Settings (NEW)
    completionWindow: Optional[int] = Field(
        None,
        alias="CompletionWindow",
        description="Days before/after due date for completion window"
    )
    requireApproval: Optional[bool] = Field(
        default=False,
        alias="RequireApproval",
        description="Requires approval to mark complete"
    )

    # Advanced Scheduling (NEW)
    deadlineOffset: Optional[int] = Field(
        None,
        alias="DeadlineOffset",
        description="Offset in days for deadline calculation"
    )

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate and sanitize chore name."""
        if not v or not v.strip():
            raise ValueError('Chore name cannot be empty or whitespace only')
        # Remove control characters except newlines/tabs
        sanitized = ''.join(char for char in v if ord(char) >= 32 or char in '\n\r\t')
        return sanitized.strip()

    @field_validator('description')
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        """Validate and sanitize description."""
        if v is None:
            return None
        # Remove control characters except newlines/tabs
        sanitized = ''.join(char for char in v if ord(char) >= 32 or char in '\n\r\t')
        return sanitized.strip() if sanitized.strip() else None

    @field_validator('dueDate')
    @classmethod
    def validate_due_date(cls, v: Optional[str]) -> Optional[str]:
        """Validate date format (ISO 8601 or YYYY-MM-DD)."""
        if v is None:
            return v

        # Try parsing as ISO 8601 / RFC3339
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except ValueError:
            pass

        # Try parsing as YYYY-MM-DD
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError(
                'dueDate must be in RFC3339 format (e.g., 2025-11-10T00:00:00Z) '
                'or YYYY-MM-DD format (e.g., 2025-11-10)'
            )

    @field_validator('frequencyType')
    @classmethod
    def validate_frequency_type(cls, v: Optional[str]) -> Optional[str]:
        """Validate frequency type."""
        if v is None:
            return "once"
        valid_types = [
            "once",
            "daily",
            "weekly",
            "monthly",
            "yearly",
            "interval_based",
            "interval",
            "days_of_the_week",
            "day_of_the_month",
            "adaptive",
            "trigger",
            "no_repeat"
        ]
        if v.lower() not in valid_types:
            raise ValueError(
                f'frequencyType must be one of: {", ".join(valid_types)}'
            )
        return v.lower()

    @field_validator('assignStrategy')
    @classmethod
    def validate_assign_strategy(cls, v: Optional[str]) -> Optional[str]:
        """Validate assignment strategy."""
        if v is None:
            return "least_completed"
        valid_strategies = ["least_completed", "round_robin", "random"]
        if v.lower() not in valid_strategies:
            raise ValueError(
                f'assignStrategy must be one of: {", ".join(valid_strategies)}'
            )
        return v.lower()


class ChoreUpdate(BaseModel):
    """Model for updating a chore (Premium feature)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Take out recycling",
                "description": "Biweekly recycling collection",
                "nextDueDate": "2025-11-17",
            }
        }
    )

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None)
    nextDueDate: Optional[str] = Field(None)


class Chore(BaseModel):
    """Complete chore model as returned by the API."""

    model_config = ConfigDict(populate_by_name=True)

    id: int = Field(..., description="Chore ID")
    name: str = Field(..., description="Chore name")
    description: Optional[str] = Field(None, description="Chore description")
    frequencyType: str = Field(..., description="Frequency type (once, daily, weekly, etc)")
    frequency: int = Field(..., description="Frequency value")
    frequencyMetadata: Optional[dict[str, Any]] = Field(None, description="Frequency metadata")
    nextDueDate: Optional[str] = Field(None, description="Next due date (ISO 8601)")
    isRolling: bool = Field(default=False, description="Is rolling schedule")
    assignedTo: int = Field(..., description="User ID of assigned user")
    assignees: list[Assignee] = Field(default_factory=list, description="List of assignees")
    assignStrategy: str = Field(
        default="least_completed",
        description="Assignment strategy",
    )
    isActive: bool = Field(default=True, description="Is chore active")
    notification: bool = Field(default=False, description="Enable notifications")
    notificationMetadata: Optional[NotificationMetadata] = Field(
        None,
        description="Notification settings",
    )
    labels: Optional[list[str]] = Field(None, description="Legacy labels")
    labelsV2: list[Label] = Field(default_factory=list, description="Chore labels")
    circleId: int = Field(..., description="Circle/household ID")
    createdAt: str = Field(..., description="Creation timestamp (ISO 8601)")
    updatedAt: str = Field(..., description="Last update timestamp (ISO 8601)")
    createdBy: int = Field(..., description="Creator user ID")
    updatedBy: Optional[int] = Field(None, description="Last updater user ID")
    status: Optional[Any] = Field(None, description="Chore status (can be string or int)")
    priority: Optional[int] = Field(None, ge=0, le=4, description="Priority (0=unset, 1=lowest, 4=highest)")
    isPrivate: bool = Field(default=False, description="Is private chore")
    points: Optional[int] = Field(None, description="Points awarded")
    subTasks: list[Any] = Field(default_factory=list, description="Sub-tasks")
    thingChore: Optional[dict[str, Any]] = Field(None, description="Thing chore metadata")
    completionWindow: Optional[int] = Field(None, description="Days before/after due date for completion window")
    requireApproval: Optional[bool] = Field(None, description="Requires approval to mark complete")
    deadlineOffset: Optional[int] = Field(None, description="Offset in days for deadline calculation")


class CircleMember(BaseModel):
    """Circle member model."""

    model_config = ConfigDict(populate_by_name=True)

    id: int = Field(..., description="Circle member ID")
    userId: int = Field(..., description="User ID")
    circleId: int = Field(..., description="Circle ID")
    role: str = Field(..., description="Member role (admin, member)")
    isActive: bool = Field(..., description="Whether member is active")
    username: str = Field(..., description="Username")
    displayName: Optional[str] = Field(None, description="Display name")
    image: Optional[str] = Field(None, description="Profile image URL")
    points: Optional[int] = Field(0, description="Member points")
    pointsRedeemed: Optional[int] = Field(0, description="Points redeemed")


class APIError(BaseModel):
    """API error response model."""

    error: str = Field(..., description="Error message")
    code: Optional[int] = Field(None, description="Error code")
    details: Optional[dict[str, Any]] = Field(None, description="Additional error details")
