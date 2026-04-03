"""
Device management module.
Handles the operational state of managed devices, beacon intervals,
cookies, and communication protocols.
"""

from config import VALID_BEACON_INTERVALS, VALID_COMMUNICATION_PROTOCOLS


class DeviceManager:
    """Manages device state, beacon interval, cookies, and communication protocol."""

    # Sample device data representing managed endpoints.
    DEFAULT_DEVICES: list[dict[str, str]] = [
        {"name": "device-alpha", "ip": "192.168.1.10", "status": "online"},
        {"name": "device-beta", "ip": "192.168.1.20", "status": "online"},
        {"name": "device-gamma", "ip": "192.168.1.30", "status": "offline"},
    ]

    def __init__(self) -> None:
        self.devices: list[dict[str, str]] = list(self.DEFAULT_DEVICES)
        self.current_beacon_interval: int = VALID_BEACON_INTERVALS[0]
        self.current_communication_protocol: str = VALID_COMMUNICATION_PROTOCOLS[1]
        self.cookies: dict[str, str] = {
            "session_id": "abc123def456",
            "auth_token": "tok_7890xyz",
            "tracking_id": "trk_001",
        }

    def show_devices(self) -> str:
        """Return a formatted string listing all managed devices."""
        if not self.devices:
            return "No devices are currently registered."

        lines: list[str] = ["**Managed Devices:**"]
        for device in self.devices:
            status_emoji = "🟢" if device["status"] == "online" else "🔴"
            lines.append(
                f"{status_emoji} **{device['name']}** — "
                f"IP: `{device['ip']}` — Status: {device['status']}"
            )
        return "\n".join(lines)

    def set_beacon_interval(self, interval: int) -> str:
        """
        Set the beacon interval to the given value.
        Returns a success message or an error if the value is invalid.
        """
        if interval not in VALID_BEACON_INTERVALS:
            allowed = ", ".join(str(v) for v in VALID_BEACON_INTERVALS)
            return (
                f"❌ Invalid beacon interval `{interval}`. "
                f"Allowed values: {allowed}."
            )

        self.current_beacon_interval = interval
        return f"✅ Beacon interval set to **{interval}** seconds."

    def request_cookies(self) -> str:
        """Return a formatted string listing all current cookies."""
        if not self.cookies:
            return "No cookies are currently stored."

        lines: list[str] = ["**Current Cookies:**"]
        for cookie_name, cookie_value in self.cookies.items():
            lines.append(f"🍪 `{cookie_name}` = `{cookie_value}`")
        return "\n".join(lines)

    def set_communication_protocol(self, protocol: str) -> str:
        """
        Set the communication protocol.
        Returns a success message or an error if the protocol is invalid.
        """
        protocol_lower = protocol.lower()
        if protocol_lower not in VALID_COMMUNICATION_PROTOCOLS:
            allowed = ", ".join(VALID_COMMUNICATION_PROTOCOLS)
            return (
                f"❌ Invalid protocol `{protocol}`. "
                f"Allowed values: {allowed}."
            )

        self.current_communication_protocol = protocol_lower
        return f"✅ Communication protocol set to **{protocol_lower}**."
