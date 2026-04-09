"""Tests for the CommandHandler (server-side state management)."""

import pytest
from datetime import datetime, timezone

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from command_handler import CommandHandler
from models import DeviceInfo


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def handler() -> CommandHandler:
    """Create a fresh CommandHandler for each test."""
    return CommandHandler()


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestInitialisation:
    """Tests for CommandHandler initialisation."""

    def test_has_default_config(self, handler: CommandHandler) -> None:
        assert handler.server_config.beacon_interval == 2
        assert handler.server_config.communication_protocol == "https"

    def test_seeds_sample_devices(self, handler: CommandHandler) -> None:
        assert len(handler.devices) == 3
        assert "device-alpha" in handler.devices
        assert "device-beta" in handler.devices
        assert "device-gamma" in handler.devices

    def test_sample_device_has_cookies(self, handler: CommandHandler) -> None:
        alpha = handler.devices["device-alpha"]
        assert "session_id" in alpha.cookies
        assert "auth_token" in alpha.cookies

    def test_gamma_is_offline(self, handler: CommandHandler) -> None:
        gamma = handler.devices["device-gamma"]
        assert gamma.status == "offline"


# ---------------------------------------------------------------------------
# Device registration
# ---------------------------------------------------------------------------

class TestDeviceRegistration:
    """Tests for register_device and get_device."""

    def test_register_new_device(self, handler: CommandHandler) -> None:
        device = DeviceInfo(name="new-dev", ip="10.0.0.1")
        handler.register_device(device)
        assert "new-dev" in handler.devices
        assert handler.devices["new-dev"].ip == "10.0.0.1"

    def test_register_updates_existing(self, handler: CommandHandler) -> None:
        device = DeviceInfo(name="device-alpha", ip="10.0.0.99")
        handler.register_device(device)
        assert handler.devices["device-alpha"].ip == "10.0.0.99"

    def test_register_updates_last_seen(self, handler: CommandHandler) -> None:
        before = datetime.now(timezone.utc)
        device = DeviceInfo(name="device-alpha", ip="10.0.0.1")
        handler.register_device(device)
        assert handler.devices["device-alpha"].last_seen >= before

    def test_get_device_returns_device(self, handler: CommandHandler) -> None:
        device = handler.get_device("device-alpha")
        assert device is not None
        assert device.name == "device-alpha"

    def test_get_device_returns_none_for_unknown(
        self, handler: CommandHandler
    ) -> None:
        assert handler.get_device("no-such-device") is None

    def test_register_device_with_cookies(
        self, handler: CommandHandler
    ) -> None:
        device = DeviceInfo(
            name="cookie-dev",
            ip="10.0.0.5",
            cookies={"session": "abc"},
        )
        handler.register_device(device)
        assert handler.devices["cookie-dev"].cookies == {"session": "abc"}
