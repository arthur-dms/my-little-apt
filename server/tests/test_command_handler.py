"""Tests for the CommandHandler."""

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from command_handler import CommandHandler
from models import CommandType, ResponseStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def handler() -> CommandHandler:
    """Create a fresh CommandHandler with sample devices."""
    return CommandHandler()


# ---------------------------------------------------------------------------
# show-devices
# ---------------------------------------------------------------------------

class TestShowDevices:
    """Tests for the show-devices command."""

    @pytest.mark.asyncio
    async def test_returns_all_devices(self, handler: CommandHandler) -> None:
        result = await handler.handle_command({
            "command": "show-devices",
            "request_id": "test-1",
        })
        assert result["status"] == ResponseStatus.SUCCESS
        assert len(result["data"]["devices"]) == 3

    @pytest.mark.asyncio
    async def test_empty_device_list(self, handler: CommandHandler) -> None:
        handler.devices.clear()
        result = await handler.handle_command({
            "command": "show-devices",
            "request_id": "test-2",
        })
        assert result["status"] == ResponseStatus.SUCCESS
        assert result["data"]["devices"] == []
        assert "0 device" in result["message"]

    @pytest.mark.asyncio
    async def test_response_includes_device_fields(
        self, handler: CommandHandler
    ) -> None:
        result = await handler.handle_command({
            "command": "show-devices",
            "request_id": "test-3",
        })
        device = result["data"]["devices"][0]
        assert "name" in device
        assert "ip" in device
        assert "status" in device
        assert "last_seen" in device


# ---------------------------------------------------------------------------
# request-cookies
# ---------------------------------------------------------------------------

class TestRequestCookies:
    """Tests for the request-cookies command."""

    @pytest.mark.asyncio
    async def test_returns_cookies_from_all_devices(
        self, handler: CommandHandler
    ) -> None:
        result = await handler.handle_command({
            "command": "request-cookies",
            "request_id": "test-4",
        })
        assert result["status"] == ResponseStatus.SUCCESS
        cookies = result["data"]["cookies_by_device"]
        # device-alpha and device-beta have cookies; gamma does not.
        assert "device-alpha" in cookies
        assert "device-beta" in cookies
        assert "device-gamma" not in cookies

    @pytest.mark.asyncio
    async def test_no_cookies(self, handler: CommandHandler) -> None:
        for d in handler.devices.values():
            d.cookies = {}
        result = await handler.handle_command({
            "command": "request-cookies",
            "request_id": "test-5",
        })
        assert result["status"] == ResponseStatus.SUCCESS
        assert result["data"]["cookies_by_device"] == {}
        assert "0 cookie" in result["message"]

    @pytest.mark.asyncio
    async def test_cookie_count_in_message(
        self, handler: CommandHandler
    ) -> None:
        result = await handler.handle_command({
            "command": "request-cookies",
            "request_id": "test-6",
        })
        # alpha has 2 cookies, beta has 1 = 3 total
        assert "3 cookie" in result["message"]
        assert "2 device" in result["message"]


# ---------------------------------------------------------------------------
# set-beacon-interval
# ---------------------------------------------------------------------------

class TestSetBeaconInterval:
    """Tests for the set-beacon-interval command."""

    @pytest.mark.asyncio
    async def test_valid_interval(self, handler: CommandHandler) -> None:
        for interval in [2, 4, 8, 16, 32]:
            result = await handler.handle_command({
                "command": "set-beacon-interval",
                "request_id": f"test-interval-{interval}",
                "args": {"interval": interval},
            })
            assert result["status"] == ResponseStatus.SUCCESS
            assert handler.server_config.beacon_interval == interval

    @pytest.mark.asyncio
    async def test_invalid_interval(self, handler: CommandHandler) -> None:
        result = await handler.handle_command({
            "command": "set-beacon-interval",
            "request_id": "test-invalid",
            "args": {"interval": 99},
        })
        assert result["status"] == ResponseStatus.ERROR
        assert "Invalid" in result["message"]

    @pytest.mark.asyncio
    async def test_missing_interval_arg(self, handler: CommandHandler) -> None:
        result = await handler.handle_command({
            "command": "set-beacon-interval",
            "request_id": "test-missing",
            "args": {},
        })
        assert result["status"] == ResponseStatus.ERROR
        assert "Missing" in result["message"]

    @pytest.mark.asyncio
    async def test_non_numeric_interval(
        self, handler: CommandHandler
    ) -> None:
        result = await handler.handle_command({
            "command": "set-beacon-interval",
            "request_id": "test-nan",
            "args": {"interval": "abc"},
        })
        assert result["status"] == ResponseStatus.ERROR
        assert "Invalid" in result["message"]


# ---------------------------------------------------------------------------
# set-communication-protocol
# ---------------------------------------------------------------------------

class TestSetCommunicationProtocol:
    """Tests for the set-communication-protocol command."""

    @pytest.mark.asyncio
    async def test_valid_protocols(self, handler: CommandHandler) -> None:
        for proto in ["http", "https", "dns"]:
            result = await handler.handle_command({
                "command": "set-communication-protocol",
                "request_id": f"test-proto-{proto}",
                "args": {"protocol": proto},
            })
            assert result["status"] == ResponseStatus.SUCCESS
            assert handler.server_config.communication_protocol == proto

    @pytest.mark.asyncio
    async def test_case_insensitive(self, handler: CommandHandler) -> None:
        result = await handler.handle_command({
            "command": "set-communication-protocol",
            "request_id": "test-case",
            "args": {"protocol": "HTTPS"},
        })
        assert result["status"] == ResponseStatus.SUCCESS
        assert handler.server_config.communication_protocol == "https"

    @pytest.mark.asyncio
    async def test_invalid_protocol(self, handler: CommandHandler) -> None:
        result = await handler.handle_command({
            "command": "set-communication-protocol",
            "request_id": "test-bad-proto",
            "args": {"protocol": "ftp"},
        })
        assert result["status"] == ResponseStatus.ERROR
        assert "Invalid" in result["message"]

    @pytest.mark.asyncio
    async def test_missing_protocol_arg(
        self, handler: CommandHandler
    ) -> None:
        result = await handler.handle_command({
            "command": "set-communication-protocol",
            "request_id": "test-missing-proto",
            "args": {},
        })
        assert result["status"] == ResponseStatus.ERROR
        assert "Missing" in result["message"]


# ---------------------------------------------------------------------------
# Invalid / unknown commands
# ---------------------------------------------------------------------------

class TestInvalidCommands:
    """Tests for malformed or unknown commands."""

    @pytest.mark.asyncio
    async def test_unknown_command(self, handler: CommandHandler) -> None:
        result = await handler.handle_command({
            "command": "self-destruct",
            "request_id": "test-unknown",
        })
        assert result["status"] == ResponseStatus.ERROR

    @pytest.mark.asyncio
    async def test_missing_command_field(
        self, handler: CommandHandler
    ) -> None:
        result = await handler.handle_command({
            "request_id": "test-no-cmd",
        })
        assert result["status"] == ResponseStatus.ERROR

    @pytest.mark.asyncio
    async def test_request_id_preserved(
        self, handler: CommandHandler
    ) -> None:
        result = await handler.handle_command({
            "command": "show-devices",
            "request_id": "preserve-me",
        })
        assert result["request_id"] == "preserve-me"


# ---------------------------------------------------------------------------
# Device registration
# ---------------------------------------------------------------------------

class TestDeviceRegistration:
    """Tests for the register_device / get_device methods."""

    def test_register_new_device(self, handler: CommandHandler) -> None:
        from models import DeviceInfo

        device = DeviceInfo(name="new-device", ip="10.0.0.1")
        handler.register_device(device)
        assert handler.get_device("new-device") is not None
        assert handler.get_device("new-device").ip == "10.0.0.1"

    def test_update_existing_device(self, handler: CommandHandler) -> None:
        from models import DeviceInfo

        device = DeviceInfo(name="device-alpha", ip="10.0.0.99")
        handler.register_device(device)
        assert handler.get_device("device-alpha").ip == "10.0.0.99"

    def test_get_nonexistent_device(self, handler: CommandHandler) -> None:
        assert handler.get_device("does-not-exist") is None
