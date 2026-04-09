"""
Command handler for the C2 server.
Manages server-side state: devices, configuration, and pending tasks.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from models import DeviceInfo, ServerConfig

logger = logging.getLogger("c2-server.handler")


class CommandHandler:
    """Manages server-side state for devices and configuration."""

    def __init__(self) -> None:
        self.server_config = ServerConfig()
        self.devices: dict[str, DeviceInfo] = {}
        self.pending_tasks: list[dict[str, Any]] = []

        # Seed sample devices for demonstration.
        self._seed_sample_devices()

    def _seed_sample_devices(self) -> None:
        """Populate the device registry with sample data."""
        samples = [
            DeviceInfo(
                name="device-alpha",
                ip="192.168.1.10",
                status="online",
                cookies={"session_id": "abc123def456", "auth_token": "tok_7890xyz"},
            ),
            DeviceInfo(
                name="device-beta",
                ip="192.168.1.20",
                status="online",
                cookies={"tracking_id": "trk_001"},
            ),
            DeviceInfo(
                name="device-gamma",
                ip="192.168.1.30",
                status="offline",
                cookies={},
            ),
        ]
        for device in samples:
            self.devices[device.name] = device

    def register_device(self, device: DeviceInfo) -> None:
        """Register or update a device in the registry."""
        device.last_seen = datetime.now(timezone.utc)
        self.devices[device.name] = device
        logger.info("Device registered/updated: %s (%s)", device.name, device.ip)

    def get_device(self, name: str) -> DeviceInfo | None:
        """Look up a device by name."""
        return self.devices.get(name)
