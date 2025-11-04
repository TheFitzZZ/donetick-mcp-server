"""Donetick API client with rate limiting and retry logic."""

import asyncio
import json as json_lib
import logging
import random
import time
from typing import Any, Dict, Optional, Tuple

import httpx

from .config import config
from .models import Chore, ChoreCreate, ChoreUpdate, CircleMember, Label

logger = logging.getLogger(__name__)


class TokenBucket:
    """Token bucket rate limiter."""

    def __init__(self, rate: float, capacity: int):
        """
        Initialize token bucket.

        Args:
            rate: Tokens per second refill rate
            capacity: Maximum token capacity
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_update = time.time()
        self.lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1):
        """
        Acquire tokens, waiting if necessary.

        Args:
            tokens: Number of tokens to acquire
        """
        async with self.lock:
            while True:
                now = time.time()
                elapsed = now - self.last_update

                # Refill tokens based on elapsed time
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                self.last_update = now

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return

                # Wait until enough tokens available
                wait_time = (tokens - self.tokens) / self.rate
                await asyncio.sleep(wait_time)


class DonetickClient:
    """Async client for Donetick external API (eAPI)."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        rate_limit_per_second: Optional[float] = None,
        rate_limit_burst: Optional[int] = None,
        cache_ttl: float = 60.0,
    ):
        """
        Initialize Donetick API client.

        Args:
            base_url: Donetick instance URL (defaults to config)
            username: Donetick username (defaults to config)
            password: Donetick password (defaults to config)
            rate_limit_per_second: Rate limit in requests per second (defaults to config)
            rate_limit_burst: Maximum burst size (defaults to config)
            cache_ttl: Cache time-to-live in seconds (default: 60.0)
        """
        self.base_url = (base_url or config.donetick_base_url).rstrip("/")
        self.username = username or config.donetick_username
        self.password = password or config.donetick_password
        self._jwt_token: Optional[str] = None
        self.rate_limiter = TokenBucket(
            rate=rate_limit_per_second or config.rate_limit_per_second,
            capacity=rate_limit_burst or config.rate_limit_burst,
        )

        # Chore caching to optimize get_chore performance
        self._chore_cache: Dict[int, Tuple[float, Chore]] = {}
        self._cache_ttl = cache_ttl

        # Configure httpx client with connection pooling and timeouts
        self.client = httpx.AsyncClient(
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=50,
                keepalive_expiry=30.0,
            ),
            timeout=httpx.Timeout(
                connect=5.0,
                read=30.0,
                write=5.0,
                pool=2.0,
            ),
            verify=True,  # Enforce certificate verification
        )

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup."""
        await self.close()

    async def close(self):
        """Close the HTTP client and cleanup resources."""
        if self.client:
            await self.client.aclose()

    async def login(self):
        """
        Authenticate with Donetick API and retrieve JWT token.

        Makes a POST request to /api/v1/auth/login with username and password,
        then stores the returned JWT token for subsequent requests.

        Raises:
            httpx.HTTPError: On authentication failure
            ValueError: If login response doesn't contain token
        """
        url = f"{self.base_url}/api/v1/auth/login"

        logger.debug("Authenticating with Donetick API")

        try:
            response = await self.client.post(
                url,
                json={
                    "username": self.username,
                    "password": self.password,
                }
            )
            response.raise_for_status()

            data = response.json()

            if "token" not in data:
                logger.error("Login response missing 'token' field")
                raise ValueError("Invalid login response: missing token")

            self._jwt_token = data["token"]

            # Update client headers with Bearer token
            self.client.headers["Authorization"] = f"Bearer {self._jwt_token}"

            logger.info("Successfully authenticated with Donetick API")

        except httpx.HTTPStatusError as e:
            logger.error(f"Authentication failed: {e.response.status_code}")
            raise
        except json_lib.JSONDecodeError as e:
            logger.error("Invalid JSON response from login endpoint")
            raise ValueError(f"Invalid JSON response from login: {e}") from e

    async def _request(
        self,
        method: str,
        path: str,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> dict[str, Any] | list[Any]:
        """
        Make HTTP request with rate limiting and retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: API endpoint path
            max_retries: Maximum number of retry attempts
            **kwargs: Additional arguments for httpx request

        Returns:
            JSON response data

        Raises:
            httpx.HTTPError: On HTTP errors after all retries exhausted
        """
        # Ensure we have a valid JWT token (lazy initialization)
        if self._jwt_token is None:
            await self.login()

        url = f"{self.base_url}{path}"
        base_delay = 1.0
        auth_retry_attempted = False

        for attempt in range(max_retries):
            try:
                # Wait for rate limit
                await self.rate_limiter.acquire()

                # Make request
                logger.debug(f"Request {method} {url} (attempt {attempt + 1}/{max_retries})")
                response = await self.client.request(method, url, **kwargs)

                # Handle rate limit responses
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", "60")
                    wait_time = float(retry_after)
                    logger.warning(f"Rate limited, waiting {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue

                # Handle authentication errors (401 Unauthorized)
                if response.status_code == 401:
                    if not auth_retry_attempted:
                        logger.warning("Authentication failed (401), refreshing JWT token")
                        auth_retry_attempted = True
                        await self.login()
                        continue
                    else:
                        logger.error("Authentication failed after token refresh")
                        raise httpx.HTTPStatusError(
                            "Authentication failed: Invalid credentials or expired session",
                            request=response.request,
                            response=response
                        )

                # Raise for other HTTP errors
                response.raise_for_status()

                # Parse JSON response with error handling
                try:
                    return response.json()
                except json_lib.JSONDecodeError as e:
                    logger.error(f"Invalid JSON response from {url}: {response.text[:200]}")
                    raise ValueError(f"Invalid JSON response from API: {e}") from e

            except httpx.TimeoutException as e:
                if attempt == max_retries - 1:
                    logger.error(f"Request timeout after {max_retries} attempts: {e}")
                    raise

                # Exponential backoff with jitter
                delay = min(base_delay * (2**attempt), 60.0)
                jitter = delay * random.uniform(-0.25, 0.25)
                wait_time = delay + jitter

                logger.warning(f"Timeout on attempt {attempt + 1}, retrying in {wait_time:.2f}s")
                await asyncio.sleep(wait_time)

            except httpx.HTTPStatusError as e:
                # Don't retry client errors (4xx) except 429 and 401
                if 400 <= e.response.status_code < 500 and e.response.status_code not in (429, 401):
                    logger.error(f"Client error: {e.response.status_code} - {e.response.text}")
                    raise

                # Retry server errors (5xx)
                if attempt == max_retries - 1:
                    logger.error(f"Server error after {max_retries} attempts: {e}")
                    raise

                delay = min(base_delay * (2**attempt), 60.0)
                jitter = delay * random.uniform(-0.25, 0.25)
                wait_time = delay + jitter

                logger.warning(
                    f"Server error on attempt {attempt + 1}, retrying in {wait_time:.2f}s"
                )
                await asyncio.sleep(wait_time)

        raise Exception(f"Failed after {max_retries} retries")

    async def list_chores(
        self,
        filter_active: Optional[bool] = None,
        assigned_to_user_id: Optional[int] = None,
    ) -> list[Chore]:
        """
        List all chores with optional filtering.

        Args:
            filter_active: Filter by active status (None = all)
            assigned_to_user_id: Filter by assigned user ID (None = all)

        Returns:
            List of Chore objects
        """
        logger.info("Fetching chores list")
        data = await self._request("GET", "/api/v1/chores/")

        # API returns {'res': [chores]} format
        chores_list = data.get('res', []) if isinstance(data, dict) else data

        # Parse response into Chore objects
        chores = [Chore(**chore_data) for chore_data in chores_list]

        # Apply filters
        if filter_active is not None:
            chores = [c for c in chores if c.isActive == filter_active]
            logger.debug(f"Filtered to active={filter_active}: {len(chores)} chores")

        if assigned_to_user_id is not None:
            chores = [c for c in chores if c.assignedTo == assigned_to_user_id]
            logger.debug(f"Filtered to user {assigned_to_user_id}: {len(chores)} chores")

        logger.info(f"Retrieved {len(chores)} chores")
        return chores

    async def get_chore(self, chore_id: int) -> Optional[Chore]:
        """
        Get a specific chore by ID with caching.

        Uses GET /api/v1/chores/{id} endpoint which includes sub-tasks.

        Args:
            chore_id: Chore ID

        Returns:
            Chore object if found (including sub-tasks), None otherwise
        """
        # Check cache
        if chore_id in self._chore_cache:
            timestamp, chore = self._chore_cache[chore_id]
            if time.time() - timestamp < self._cache_ttl:
                logger.debug(f"Cache hit for chore {chore_id}")
                return chore
            else:
                logger.debug(f"Cache expired for chore {chore_id}")

        # Cache miss or expired - fetch specific chore (includes sub-tasks!)
        logger.info(f"Fetching chore {chore_id} directly (includes sub-tasks)")

        try:
            data = await self._request("GET", f"/api/v1/chores/{chore_id}")

            # API returns {'res': chore} format, unwrap it
            chore_data = data.get('res', data) if isinstance(data, dict) else data
            chore = Chore(**chore_data)

            # Cache the result
            self._chore_cache[chore_id] = (time.time(), chore)

            logger.info(f"Found chore {chore_id}: {chore.name}")
            return chore

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Chore {chore_id} not found")
                return None
            raise

    def clear_cache(self):
        """Clear the chore cache."""
        self._chore_cache.clear()
        logger.debug("Chore cache cleared")

    async def create_chore(self, chore: ChoreCreate) -> Chore:
        """
        Create a new chore.

        Args:
            chore: ChoreCreate object with chore details

        Returns:
            Created Chore object
        """
        logger.info(f"Creating chore: {chore.name}")
        data = await self._request("POST", "/api/v1/chores/", json=chore.model_dump(exclude_none=True))

        # API returns {'res': chore_id} on successful creation
        chore_id = data.get('res') if isinstance(data, dict) else None

        if chore_id is None:
            raise ValueError("Failed to get chore ID from create response")

        logger.info(f"Created chore with ID: {chore_id}")

        # Fetch the created chore to return full details
        created_chore = await self.get_chore(chore_id)

        if created_chore is None:
            raise ValueError(f"Failed to fetch created chore {chore_id}")

        logger.info(f"Fetched created chore {created_chore.id}: {created_chore.name}")
        return created_chore

    async def update_chore(self, chore_id: int, update: ChoreUpdate) -> Chore:
        """
        Update an existing chore.

        Note: This is a Premium/Plus feature.

        Args:
            chore_id: Chore ID to update
            update: ChoreUpdate object with fields to update

        Returns:
            Updated Chore object
        """
        logger.info(f"Updating chore {chore_id}")
        data = await self._request(
            "PUT",
            f"/api/v1/chores/{chore_id}",
            json=update.model_dump(exclude_none=True),
        )

        updated_chore = Chore(**data)
        logger.info(f"Updated chore {chore_id}: {updated_chore.name}")
        return updated_chore

    async def delete_chore(self, chore_id: int) -> bool:
        """
        Delete a chore.

        Note: Only the chore creator can delete a chore.

        Args:
            chore_id: Chore ID to delete

        Returns:
            True if deletion successful
        """
        logger.info(f"Deleting chore {chore_id}")
        await self._request("DELETE", f"/api/v1/chores/{chore_id}")
        logger.info(f"Deleted chore {chore_id}")
        return True

    async def complete_chore(
        self,
        chore_id: int,
        completed_by: Optional[int] = None,
    ) -> Chore:
        """
        Mark a chore as complete.

        Note: This is a Premium/Plus feature.

        Args:
            chore_id: Chore ID to complete
            completed_by: User ID who completed the chore (optional)

        Returns:
            Updated Chore object
        """
        logger.info(f"Completing chore {chore_id}")

        params = {}
        if completed_by is not None:
            params["completedBy"] = completed_by

        data = await self._request(
            "POST",
            f"/api/v1/chores/{chore_id}/do",
            params=params,
        )

        completed_chore = Chore(**data)
        logger.info(f"Completed chore {chore_id}: {completed_chore.name}")
        return completed_chore

    async def get_circle_members(self) -> list[CircleMember]:
        """
        Get all members in the user's circle.

        Note: This is a Premium/Plus feature.

        Returns:
            List of CircleMember objects
        """
        logger.info("Fetching circle members")
        data = await self._request("GET", "/api/v1/circles/members")

        # API returns {'res': [...]} format
        members_data = data.get('res', data) if isinstance(data, dict) else data
        members = [CircleMember(**member_data) for member_data in members_data]
        logger.info(f"Retrieved {len(members)} circle members")
        return members

    async def get_labels(self) -> list[Label]:
        """
        Get all labels in the user's circle.

        Returns:
            List of Label objects
        """
        logger.info("Fetching labels")
        data = await self._request("GET", "/api/v1/labels")

        # API returns {'res': [...]} format
        labels_data = data.get('res', data) if isinstance(data, dict) else data
        labels = [Label(**label_data) for label_data in labels_data]
        logger.info(f"Retrieved {len(labels)} labels")
        return labels

    async def create_label(self, name: str, color: Optional[str] = None) -> Label:
        """
        Create a new label.

        Args:
            name: Label name (required)
            color: Label color in hex format (e.g., "#80d8ff"), optional

        Returns:
            Created Label object
        """
        logger.info(f"Creating label: {name}")

        payload = {"name": name}
        if color:
            payload["color"] = color

        data = await self._request("POST", "/api/v1/labels", json=payload)

        # API returns {'res': label} format
        label_data = data.get('res', data) if isinstance(data, dict) else data
        label = Label(**label_data)
        logger.info(f"Created label with ID: {label.id}")
        return label

    async def update_label(self, label_id: int, name: str, color: Optional[str] = None) -> Label:
        """
        Update an existing label.

        Args:
            label_id: Label ID to update
            name: New label name
            color: New label color in hex format, optional

        Returns:
            Updated Label object
        """
        logger.info(f"Updating label {label_id}")

        payload = {
            "id": label_id,
            "name": name
        }
        if color:
            payload["color"] = color

        data = await self._request("PUT", "/api/v1/labels", json=payload)

        # API returns {'res': label} format
        label_data = data.get('res', data) if isinstance(data, dict) else data
        label = Label(**label_data)
        logger.info(f"Updated label {label_id}")
        return label

    async def delete_label(self, label_id: int) -> bool:
        """
        Delete a label.

        Args:
            label_id: Label ID to delete

        Returns:
            True if successful
        """
        logger.info(f"Deleting label {label_id}")
        await self._request("DELETE", f"/api/v1/labels/{label_id}")
        logger.info(f"Deleted label {label_id}")
        return True
