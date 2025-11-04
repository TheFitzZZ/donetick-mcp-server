#!/usr/bin/env python3
"""
Import chores from tests/chores.json into Donetick test environment.

This script:
1. Reads the chores.json file with custom field formats
2. Maps usernames to user IDs in the test environment
3. Transforms fields to API-compatible format
4. Creates chores with full feature support including sub-tasks
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from donetick_mcp.client import DonetickClient
from donetick_mcp.models import ChoreCreate

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'chore_import_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)

logger = logging.getLogger(__name__)


class ChoreImporter:
    """Import chores from JSON file with username mapping."""

    def __init__(self, client: DonetickClient):
        self.client = client
        self.username_to_id: Dict[str, int] = {}
        self.label_name_to_id: Dict[str, int] = {}
        self.created_chores: List[int] = []
        self.failed_chores: List[tuple] = []

    async def load_user_mapping(self):
        """Load circle members and create username to ID mapping."""
        logger.info("Loading circle members for username mapping")

        try:
            members = await self.client.get_circle_members()

            for member in members:
                username = member.displayName or member.username
                self.username_to_id[username] = member.userID
                logger.info(f"Mapped user: {username} -> ID {member.userID}")

            logger.info(f"Loaded {len(self.username_to_id)} user mappings")
            return True

        except Exception as e:
            logger.error(f"Failed to load circle members: {e}")
            logger.warning("Will use default test user mappings")

            # Fallback to known test users (based on displayName from circle members)
            self.username_to_id = {
                "Tyler": 7,         # test (admin)
                "Owen": 9,          # test-bravo
                "Eli": 10,          # test-alpha
                "Elyse": 11,        # test-charlie (was 7, now unique!)
            }
            logger.info(f"Using fallback mappings: {self.username_to_id}")
            return False

    async def load_label_mapping(self):
        """Load labels and create name to ID mapping."""
        logger.info("Loading labels for label mapping")

        try:
            labels = await self.client.get_labels()

            for label in labels:
                # Map by name (case-insensitive)
                label_name = label.name.lower().strip()
                self.label_name_to_id[label_name] = label.id
                logger.info(f"Mapped label: '{label.name}' -> ID {label.id}")

            logger.info(f"Loaded {len(self.label_name_to_id)} label mappings")
            return True

        except Exception as e:
            logger.error(f"Failed to load labels: {e}")
            logger.warning("Will proceed without label mapping")
            return False

    def map_labels(self, label_names: Optional[List[str]]) -> List[dict]:
        """Map label names to labelsV2 format with IDs."""
        if not label_names:
            return []

        labels_v2 = []
        for label_name in label_names:
            # Try case-insensitive match
            label_key = label_name.lower().strip()
            label_id = self.label_name_to_id.get(label_key)

            if label_id:
                labels_v2.append({"id": label_id})
                logger.debug(f"Mapped label '{label_name}' to ID {label_id}")
            else:
                logger.warning(f"Label '{label_name}' not found in available labels")

        return labels_v2

    def transform_frequency_metadata(self, metadata: dict, timezone: str = "America/New_York") -> dict:
        """Transform frequencyMetadata from file format to API format."""
        if not metadata:
            return {}

        api_metadata = {}

        # Map daysOfWeek to days array
        if "daysOfWeek" in metadata:
            day_map = {
                "Mon": "monday",
                "Tue": "tuesday",
                "Wed": "wednesday",
                "Thu": "thursday",
                "Fri": "friday",
                "Sat": "saturday",
                "Sun": "sunday"
            }
            api_metadata["days"] = [day_map[d] for d in metadata["daysOfWeek"]]

            # Add required fields for days_of_the_week frequency type
            api_metadata["unit"] = "days"
            api_metadata["timezone"] = timezone
            api_metadata["weekPattern"] = "every_week"

        # Convert dueTime to RFC3339 format with timezone
        if "dueTime" in metadata:
            # Get current date to construct full datetime
            from datetime import datetime
            import pytz

            # Parse time (format: "HH:MM")
            time_parts = metadata["dueTime"].split(":")
            hour = int(time_parts[0])
            minute = int(time_parts[1])

            # Create datetime in specified timezone
            tz = pytz.timezone(timezone)
            # Use today's date as reference
            now = datetime.now(tz)
            dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # Format as RFC3339
            api_metadata["time"] = dt.isoformat()

        # Copy duration if present
        if "durationMinutes" in metadata:
            api_metadata["durationMinutes"] = metadata["durationMinutes"]

        return api_metadata

    def transform_notification_metadata(self, metadata: dict) -> dict:
        """Transform notificationMetadata from file format to API format."""
        if not metadata:
            return {}

        templates = []

        # offsetMinutes becomes a template
        if "offsetMinutes" in metadata:
            offset = metadata["offsetMinutes"]
            if offset != 0:
                # Negative offset = before due (positive value in template)
                # Positive offset = after due (positive value in template)
                templates.append({
                    "value": offset,  # Can be negative (before) or positive (after)
                    "unit": "m"  # minutes
                })

        # remindAtDueTime adds a template at due time
        if metadata.get("remindAtDueTime"):
            templates.append({
                "value": 0,
                "unit": "m"
            })

        return {"templates": templates} if templates else {}

    def transform_subtasks(self, subtasks: List[str]) -> List[dict]:
        """Transform subtask strings to API format."""
        if not subtasks:
            return []

        return [
            {
                "orderId": i,
                "name": task,
                "completedAt": None,
                "completedBy": 0,
                "parentId": None
            }
            for i, task in enumerate(subtasks)
        ]

    def map_assignees(self, usernames: List[str]) -> tuple[int, List[dict]]:
        """Map usernames to assignees list and primary assignedTo."""
        if not usernames:
            return None, []

        user_ids = []
        for username in usernames:
            user_id = self.username_to_id.get(username)
            if user_id:
                user_ids.append(user_id)
            else:
                logger.warning(f"Unknown username: {username}")

        if not user_ids:
            logger.warning(f"No valid user IDs found for usernames: {usernames}")
            return None, []

        # Primary assignee is first user
        assigned_to = user_ids[0]

        # Build assignees list
        assignees = [{"userId": uid} for uid in user_ids]

        return assigned_to, assignees

    def calculate_next_due_date(self, frequency_type: str, freq_metadata: dict, freq_metadata_json: dict) -> str:
        """Calculate next due date based on frequency type and metadata."""
        import pytz
        from datetime import datetime

        if frequency_type == "once":
            # One-time chores - set to tomorrow
            return (datetime.now() + timedelta(days=1)).isoformat() + "Z"

        elif frequency_type == "days_of_the_week":
            # Get timezone
            timezone = freq_metadata.get("timezone", "America/New_York")
            tz = pytz.timezone(timezone)

            # Get current time in target timezone
            now = datetime.now(tz)

            # Get days of week (already transformed to lowercase full names)
            days = freq_metadata.get("days", [])
            if not days:
                # Fallback to tomorrow
                return (datetime.now() + timedelta(days=1)).isoformat() + "Z"

            # Map day names to weekday numbers (0=Monday, 6=Sunday)
            day_map = {
                "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                "friday": 4, "saturday": 5, "sunday": 6
            }

            # Get target weekday for first day in list
            first_day = days[0]
            target_weekday = day_map.get(first_day, 0)

            # Parse time from frequencyMetadata (RFC3339 format)
            time_str = freq_metadata.get("time", "")
            if time_str:
                # Extract hour and minute from RFC3339 time
                try:
                    time_dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    target_hour = time_dt.hour
                    target_minute = time_dt.minute
                except:
                    # Fallback to parsing from original format
                    due_time = freq_metadata_json.get("dueTime", "12:00")
                    time_parts = due_time.split(":")
                    target_hour = int(time_parts[0])
                    target_minute = int(time_parts[1])
            else:
                target_hour = 12
                target_minute = 0

            # Calculate next occurrence
            current_weekday = now.weekday()
            days_ahead = (target_weekday - current_weekday) % 7

            # If it's the same day, check if time has passed
            if days_ahead == 0:
                target_time = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
                if now >= target_time:
                    # Time has passed today, schedule for next week
                    days_ahead = 7

            # Calculate the due date
            next_due = now + timedelta(days=days_ahead)
            next_due = next_due.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)

            # Return in UTC ISO format
            return next_due.astimezone(pytz.UTC).isoformat().replace('+00:00', 'Z')

        elif frequency_type == "daily":
            # Daily chores - set to tomorrow at specified time
            timezone = freq_metadata.get("timezone", "America/New_York")
            tz = pytz.timezone(timezone)
            now = datetime.now(tz)

            # Parse time
            time_str = freq_metadata.get("time", "")
            if time_str:
                try:
                    time_dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    target_hour = time_dt.hour
                    target_minute = time_dt.minute
                except:
                    target_hour = 12
                    target_minute = 0
            else:
                target_hour = 12
                target_minute = 0

            # Set to tomorrow at target time
            next_due = now + timedelta(days=1)
            next_due = next_due.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)

            return next_due.astimezone(pytz.UTC).isoformat().replace('+00:00', 'Z')

        else:
            # Fallback for other frequency types
            return (datetime.now() + timedelta(days=1)).isoformat() + "Z"

    def parse_chore(self, chore_data: dict) -> Optional[ChoreCreate]:
        """Parse chore from JSON format to ChoreCreate model."""
        try:
            # Transform frequency metadata first
            freq_metadata_json = chore_data.get("frequencyMetadata_json", {})
            freq_metadata = self.transform_frequency_metadata(freq_metadata_json)

            # Determine correct frequencyType
            # If there are specific days of the week, use "days_of_the_week" type
            frequency_type = chore_data.get("frequencyType", "once")
            if freq_metadata_json.get("daysOfWeek"):
                frequency_type = "days_of_the_week"

            # Calculate due date based on frequency type
            # IMPORTANT: API requires dueDate to calculate nextDueDate, even for recurring chores
            due_date = self.calculate_next_due_date(frequency_type, freq_metadata, freq_metadata_json)

            # Transform notification metadata
            notif_metadata = self.transform_notification_metadata(
                chore_data.get("notificationMetadata_json", {})
            )

            # Transform subtasks
            subtasks = self.transform_subtasks(
                chore_data.get("subTasks_json", [])
            )

            # Map assignees
            assigned_to, assignees = self.map_assignees(
                chore_data.get("assignees_usernames", [])
            )

            # Map labels to labelsV2 format
            labels_v2 = self.map_labels(chore_data.get("labels"))

            # Build ChoreCreate
            chore = ChoreCreate(
                name=chore_data["name"],
                description=chore_data.get("description_html"),
                dueDate=due_date,
                frequencyType=frequency_type,
                frequency=chore_data.get("frequency", 1),
                frequencyMetadata=freq_metadata if freq_metadata else None,
                isRolling=chore_data.get("isRolling", False),
                assignedTo=assigned_to,
                assignees=assignees if assignees else None,
                assignStrategy=chore_data.get("assignStrategy", "least_completed"),
                isActive=True,
                notification=chore_data.get("notification", False),
                notificationMetadata=notif_metadata if notif_metadata else None,
                labels=chore_data.get("labels"),  # Legacy format (optional)
                labelsV2=labels_v2 if labels_v2 else None,  # New format with IDs
                priority=chore_data.get("priority", 0),
                requireApproval=False,
                isPrivate=False,
                completionWindow=0,
                points=10,  # Default points
                subTasks=subtasks if subtasks else None
            )

            return chore

        except Exception as e:
            logger.error(f"Failed to parse chore '{chore_data.get('name', 'unknown')}': {e}", exc_info=True)
            return None

    async def import_chore(self, chore_data: dict, index: int, total: int) -> bool:
        """Import a single chore."""
        chore_name = chore_data.get("name", "Unknown")

        try:
            logger.info(f"[{index}/{total}] Parsing: {chore_name}")

            chore = self.parse_chore(chore_data)
            if not chore:
                self.failed_chores.append((chore_name, "Failed to parse"))
                return False

            logger.info(f"[{index}/{total}] Creating: {chore_name}")
            logger.debug(f"  Frequency: {chore.frequencyType}")
            logger.debug(f"  Assignees: {chore.assignees}")
            logger.debug(f"  Sub-tasks: {len(chore.subTasks) if chore.subTasks else 0}")

            created = await self.client.create_chore(chore)

            self.created_chores.append(created.id)
            logger.info(f"  ✓ Created chore ID {created.id}")

            if created.subTasks:
                logger.info(f"    └─ With {len(created.subTasks)} sub-tasks")

            return True

        except Exception as e:
            logger.error(f"  ✗ Failed to create '{chore_name}': {e}")
            self.failed_chores.append((chore_name, str(e)))
            return False

    async def import_from_file(self, filepath: str, limit: Optional[int] = None):
        """Import chores from JSON file."""
        logger.info(f"Loading chores from: {filepath}")

        # Read JSON file
        try:
            with open(filepath, 'r') as f:
                # Remove comments (JSON doesn't support them, but our file has them)
                content = f.read()
                # Remove /* */ style comments
                import re
                content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
                # Remove // style comments
                content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)

                data = json.loads(content)
                chores_data = data.get("chores", [])

        except Exception as e:
            logger.error(f"Failed to load JSON file: {e}")
            raise

        logger.info(f"Found {len(chores_data)} chores in file")

        # Apply limit if specified
        if limit:
            chores_data = chores_data[:limit]
            logger.info(f"Limiting import to first {limit} chores")

        # Import each chore
        for i, chore_data in enumerate(chores_data, 1):
            await self.import_chore(chore_data, i, len(chores_data))

            # Small delay to avoid rate limiting
            await asyncio.sleep(0.1)

        # Summary
        print()
        print("=" * 80)
        print("IMPORT SUMMARY")
        print("=" * 80)
        print()
        print(f"Total chores in file: {len(chores_data)}")
        print(f"Successfully created: {len(self.created_chores)}")
        print(f"Failed: {len(self.failed_chores)}")
        print()

        if self.failed_chores:
            print("Failed Chores:")
            for name, error in self.failed_chores:
                print(f"  - {name}")
                print(f"    Error: {error}")
            print()

        if self.created_chores:
            print(f"✅ Created {len(self.created_chores)} chores successfully!")
            print(f"   Chore IDs: {', '.join(map(str, self.created_chores[:10]))}")
            if len(self.created_chores) > 10:
                print(f"   ... and {len(self.created_chores) - 10} more")

        return len(self.created_chores), len(self.failed_chores)


async def main():
    """Main import function."""
    import sys

    print("=" * 80)
    print("CHORE IMPORTER - v0.2.0")
    print("=" * 80)
    print()

    # Parse arguments
    filepath = "tests/chores.json"
    limit = 5 if "--limit" in sys.argv else None  # Default to 5 for testing

    if "--all" in sys.argv:
        limit = None
    elif "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        if idx + 1 < len(sys.argv):
            limit = int(sys.argv[idx + 1])

    client = DonetickClient()

    try:
        # Step 1: Authenticate
        print("📋 Step 1: Authentication")
        print("-" * 80)
        await client.login()
        logger.info("Authenticated successfully")
        print("✓ Authenticated")
        print()

        # Step 2: Load user mapping
        print("📋 Step 2: User Mapping")
        print("-" * 80)
        importer = ChoreImporter(client)
        await importer.load_user_mapping()
        print(f"✓ Mapped {len(importer.username_to_id)} users")
        for username, uid in importer.username_to_id.items():
            print(f"  - {username} → User ID {uid}")
        print()

        # Step 3: Load label mapping
        print("📋 Step 3: Label Mapping")
        print("-" * 80)
        await importer.load_label_mapping()
        if importer.label_name_to_id:
            print(f"✓ Mapped {len(importer.label_name_to_id)} labels")
            for label_name, label_id in importer.label_name_to_id.items():
                print(f"  - {label_name} → Label ID {label_id}")
        else:
            print("⚠️  No labels found - will proceed without label mapping")
        print()

        # Step 4: Import chores
        print("📋 Step 4: Importing Chores")
        print("-" * 80)
        if limit:
            print(f"⚠️  Import limited to {limit} chores (use --all for full import)")
            print()

        created, failed = await importer.import_from_file(filepath, limit)

        # Log file
        log_files = [h.baseFilename for h in logger.handlers if isinstance(h, logging.FileHandler)]
        if log_files:
            print()
            print(f"📄 Detailed logs saved to: {log_files[0]}")

        return 0 if failed == 0 else 1

    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        print(f"\n✗ Import failed: {e}")
        return 1

    finally:
        await client.close()


if __name__ == "__main__":
    print("Usage:")
    print("  python import_chores.py           # Import first 5 chores (test mode)")
    print("  python import_chores.py --limit 10  # Import first 10 chores")
    print("  python import_chores.py --all      # Import all chores")
    print()

    exit_code = asyncio.run(main())
    sys.exit(exit_code)
