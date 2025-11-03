"""Pydantic models for Donetick API requests and responses."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class Assignee(BaseModel):
    """Chore assignee model."""

    userId: int = Field(..., description="User ID of the assignee")


class Label(BaseModel):
    """Chore label model."""

    id: int = Field(..., description="Label ID")
    name: str = Field(..., description="Label name")


class NotificationMetadata(BaseModel):
    """Notification configuration metadata."""

    nagging: bool = Field(default=False, description="Enable nagging notifications")
    predue: bool = Field(default=False, description="Enable pre-due notifications")


class ChoreCreate(BaseModel):
    """Enhanced model for creating a new chore with full feature support."""

    # Basic Information
    Name: str = Field(..., min_length=1, max_length=200, description="Chore name (required)")
    Description: Optional[str] = Field(None, max_length=5000, description="Chore description")
    DueDate: Optional[str] = Field(
        None,
        description="Due date in RFC3339 or YYYY-MM-DD format",
    )
    CreatedBy: Optional[int] = Field(None, description="User ID of creator")

    # Recurrence/Frequency Settings
    FrequencyType: Optional[str] = Field(
        default="once",
        description="Frequency type: once, daily, weekly, monthly, yearly, interval_based",
    )
    Frequency: Optional[int] = Field(
        default=1,
        ge=1,
        description="Frequency value (e.g., 1=weekly, 2=biweekly)",
    )
    FrequencyMetadata: Optional[dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional frequency configuration (e.g., days of week, time)",
    )
    IsRolling: Optional[bool] = Field(
        default=False,
        description="Rolling schedule (next due date based on completion) vs fixed schedule",
    )

    # User Assignment
    AssignedTo: Optional[int] = Field(None, description="Primary assigned user ID")
    Assignees: Optional[list[dict[str, int]]] = Field(
        default_factory=list,
        description="List of assignee objects with userId field",
    )
    AssignStrategy: Optional[str] = Field(
        default="least_completed",
        description="Assignment strategy: least_completed, round_robin, random",
    )

    # Notifications
    Notification: Optional[bool] = Field(
        default=False,
        description="Enable notifications for this chore"
    )
    NotificationMetadata: Optional[dict[str, bool]] = Field(
        default_factory=lambda: {"nagging": False, "predue": False},
        description="Notification settings: nagging (reminders), predue (before due date)",
    )

    # Organization & Priority
    Priority: Optional[int] = Field(
        None,
        ge=1,
        le=5,
        description="Priority level (1=lowest, 5=highest)"
    )
    Labels: Optional[list[str]] = Field(
        default_factory=list,
        description="Label tags for categorization"
    )
    LabelsV2: Optional[list[dict[str, Any]]] = Field(
        default_factory=list,
        description="Label objects with id and name fields",
    )

    # Status & Visibility
    IsActive: Optional[bool] = Field(
        default=True,
        description="Active status (inactive chores are hidden)"
    )
    IsPrivate: Optional[bool] = Field(
        default=False,
        description="Private chore (visible only to creator)"
    )

    # Gamification
    Points: Optional[int] = Field(
        None,
        ge=0,
        description="Points awarded for completion"
    )

    # Advanced Features
    SubTasks: Optional[list[dict[str, Any]]] = Field(
        default_factory=list,
        description="Sub-tasks/checklist items"
    )
    ThingChore: Optional[dict[str, Any]] = Field(
        None,
        description="Thing/device association metadata"
    )

    @field_validator('Name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate and sanitize chore name."""
        if not v or not v.strip():
            raise ValueError('Chore name cannot be empty or whitespace only')
        # Remove control characters except newlines/tabs
        sanitized = ''.join(char for char in v if ord(char) >= 32 or char in '\n\r\t')
        return sanitized.strip()

    @field_validator('Description')
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        """Validate and sanitize description."""
        if v is None:
            return None
        # Remove control characters except newlines/tabs
        sanitized = ''.join(char for char in v if ord(char) >= 32 or char in '\n\r\t')
        return sanitized.strip() if sanitized.strip() else None

    @field_validator('DueDate')
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
                'DueDate must be in RFC3339 format (e.g., 2025-11-10T00:00:00Z) '
                'or YYYY-MM-DD format (e.g., 2025-11-10)'
            )

    @field_validator('FrequencyType')
    @classmethod
    def validate_frequency_type(cls, v: Optional[str]) -> Optional[str]:
        """Validate frequency type."""
        if v is None:
            return "once"
        valid_types = ["once", "daily", "weekly", "monthly", "yearly", "interval_based"]
        if v.lower() not in valid_types:
            raise ValueError(
                f'FrequencyType must be one of: {", ".join(valid_types)}'
            )
        return v.lower()

    @field_validator('AssignStrategy')
    @classmethod
    def validate_assign_strategy(cls, v: Optional[str]) -> Optional[str]:
        """Validate assignment strategy."""
        if v is None:
            return "least_completed"
        valid_strategies = ["least_completed", "round_robin", "random"]
        if v.lower() not in valid_strategies:
            raise ValueError(
                f'AssignStrategy must be one of: {", ".join(valid_strategies)}'
            )
        return v.lower()

    class Config:
        json_schema_extra = {
            "example": {
                "Name": "Take out the trash",
                "Description": "Weekly trash collection on Monday mornings",
                "DueDate": "2025-11-10T09:00:00Z",
                "CreatedBy": 1,
                "FrequencyType": "weekly",
                "Frequency": 1,
                "FrequencyMetadata": {"days": [1], "time": "09:00"},
                "IsRolling": False,
                "AssignedTo": 1,
                "Assignees": [{"userId": 1}, {"userId": 2}],
                "AssignStrategy": "least_completed",
                "Notification": True,
                "NotificationMetadata": {"nagging": True, "predue": True},
                "Priority": 3,
                "Labels": ["cleaning", "outdoor"],
                "IsActive": True,
                "IsPrivate": False,
                "Points": 10,
            }
        }


class ChoreUpdate(BaseModel):
    """Model for updating a chore (Premium feature)."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None)
    nextDueDate: Optional[str] = Field(None)

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Take out recycling",
                "description": "Biweekly recycling collection",
                "nextDueDate": "2025-11-17",
            }
        }


class Chore(BaseModel):
    """Complete chore model as returned by the API."""

    id: int = Field(..., description="Chore ID")
    name: str = Field(..., description="Chore name")
    description: Optional[str] = Field(None, description="Chore description")
    frequencyType: str = Field(..., description="Frequency type (once, daily, weekly, etc)")
    frequency: int = Field(..., description="Frequency value")
    frequencyMetadata: dict[str, Any] = Field(default_factory=dict)
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
    notificationMetadata: NotificationMetadata = Field(
        default_factory=NotificationMetadata,
        description="Notification settings",
    )
    labels: Optional[list[str]] = Field(None, description="Legacy labels")
    labelsV2: list[Label] = Field(default_factory=list, description="Chore labels")
    circleId: int = Field(..., description="Circle/household ID")
    createdAt: str = Field(..., description="Creation timestamp (ISO 8601)")
    updatedAt: str = Field(..., description="Last update timestamp (ISO 8601)")
    createdBy: int = Field(..., description="Creator user ID")
    updatedBy: Optional[int] = Field(None, description="Last updater user ID")
    status: Optional[str] = Field(None, description="Chore status")
    priority: Optional[int] = Field(None, ge=1, le=5, description="Priority (1-5)")
    isPrivate: bool = Field(default=False, description="Is private chore")
    points: Optional[int] = Field(None, description="Points awarded")
    subTasks: list[Any] = Field(default_factory=list, description="Sub-tasks")
    thingChore: Optional[dict[str, Any]] = Field(None, description="Thing chore metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "name": "Take out the trash",
                "description": "Weekly trash collection",
                "frequencyType": "weekly",
                "frequency": 1,
                "frequencyMetadata": {},
                "nextDueDate": "2025-11-10T00:00:00Z",
                "isRolling": False,
                "assignedTo": 1,
                "assignees": [{"userId": 1}],
                "assignStrategy": "least_completed",
                "isActive": True,
                "notification": False,
                "notificationMetadata": {"nagging": False, "predue": False},
                "labels": None,
                "labelsV2": [],
                "circleId": 1,
                "createdAt": "2025-11-03T00:00:00Z",
                "updatedAt": "2025-11-03T00:00:00Z",
                "createdBy": 1,
                "updatedBy": 1,
                "status": "active",
                "priority": 2,
                "isPrivate": False,
                "points": None,
                "subTasks": [],
                "thingChore": None,
            }
        }


class CircleMember(BaseModel):
    """Circle member model."""

    userId: int = Field(..., description="User ID")
    userName: str = Field(..., description="User name")
    userEmail: str = Field(..., description="User email")
    role: str = Field(..., description="User role in circle")


class APIError(BaseModel):
    """API error response model."""

    error: str = Field(..., description="Error message")
    code: Optional[int] = Field(None, description="Error code")
    details: Optional[dict[str, Any]] = Field(None, description="Additional error details")
