"""Tests for the DeviceManager class."""

import pytest

from devices import DeviceManager


class TestShowDevices:
    """Tests for DeviceManager.show_devices()."""

    def test_show_devices_returns_string(self) -> None:
        manager = DeviceManager()
        result = manager.show_devices()
        assert isinstance(result, str)

    def test_show_devices_contains_header(self) -> None:
        manager = DeviceManager()
        result = manager.show_devices()
        assert "**Managed Devices:**" in result

    def test_show_devices_contains_all_device_names(self) -> None:
        manager = DeviceManager()
        result = manager.show_devices()
        for device in DeviceManager.DEFAULT_DEVICES:
            assert device["name"] in result

    def test_show_devices_contains_ip_addresses(self) -> None:
        manager = DeviceManager()
        result = manager.show_devices()
        for device in DeviceManager.DEFAULT_DEVICES:
            assert device["ip"] in result

    def test_show_devices_shows_online_emoji_for_online_devices(self) -> None:
        manager = DeviceManager()
        result = manager.show_devices()
        assert "🟢" in result

    def test_show_devices_shows_offline_emoji_for_offline_devices(self) -> None:
        manager = DeviceManager()
        result = manager.show_devices()
        assert "🔴" in result

    def test_show_devices_empty_list(self) -> None:
        manager = DeviceManager()
        manager.devices = []
        result = manager.show_devices()
        assert result == "No devices are currently registered."


class TestSetBeaconInterval:
    """Tests for DeviceManager.set_beacon_interval()."""

    @pytest.mark.parametrize("interval", [15, 30, 60, 120])
    def test_set_valid_beacon_interval(self, interval: int) -> None:
        manager = DeviceManager()
        result = manager.set_beacon_interval(interval)
        assert "✅" in result
        assert str(interval) in result
        assert manager.current_beacon_interval == interval

    @pytest.mark.parametrize("interval", [0, 1, 2, 3, 5, 7, 9, 16, 17, 31, 33, 64, -1, 100])
    def test_set_invalid_beacon_interval(self, interval: int) -> None:
        manager = DeviceManager()
        original = manager.current_beacon_interval
        result = manager.set_beacon_interval(interval)
        assert "❌" in result
        assert "Invalid" in result
        assert manager.current_beacon_interval == original

    def test_set_beacon_interval_updates_state(self) -> None:
        manager = DeviceManager()
        manager.set_beacon_interval(60)
        assert manager.current_beacon_interval == 60
        manager.set_beacon_interval(30)
        assert manager.current_beacon_interval == 30

    def test_invalid_beacon_interval_error_lists_allowed_values(self) -> None:
        manager = DeviceManager()
        result = manager.set_beacon_interval(99)
        assert "15" in result
        assert "30" in result
        assert "60" in result
        assert "120" in result


class TestRequestCookies:
    """Tests for DeviceManager.request_cookies()."""

    def test_request_cookies_returns_string(self) -> None:
        manager = DeviceManager()
        result = manager.request_cookies()
        assert isinstance(result, str)

    def test_request_cookies_contains_header(self) -> None:
        manager = DeviceManager()
        result = manager.request_cookies()
        assert "**Current Cookies:**" in result

    def test_request_cookies_contains_cookie_emoji(self) -> None:
        manager = DeviceManager()
        result = manager.request_cookies()
        assert "🍪" in result

    def test_request_cookies_contains_all_cookie_names(self) -> None:
        manager = DeviceManager()
        result = manager.request_cookies()
        for name in manager.cookies:
            assert name in result

    def test_request_cookies_contains_all_cookie_values(self) -> None:
        manager = DeviceManager()
        result = manager.request_cookies()
        for value in manager.cookies.values():
            assert value in result

    def test_request_cookies_empty(self) -> None:
        manager = DeviceManager()
        manager.cookies = {}
        result = manager.request_cookies()
        assert result == "No cookies are currently stored."


class TestSetCommunicationProtocol:
    """Tests for DeviceManager.set_communication_protocol()."""

    @pytest.mark.parametrize("protocol", ["http", "https", "dns"])
    def test_set_valid_protocol(self, protocol: str) -> None:
        manager = DeviceManager()
        result = manager.set_communication_protocol(protocol)
        assert "✅" in result
        assert protocol in result
        assert manager.current_communication_protocol == protocol

    @pytest.mark.parametrize("protocol", ["HTTP", "HTTPS", "DNS", "Http"])
    def test_set_valid_protocol_case_insensitive(self, protocol: str) -> None:
        manager = DeviceManager()
        result = manager.set_communication_protocol(protocol)
        assert "✅" in result
        assert manager.current_communication_protocol == protocol.lower()

    @pytest.mark.parametrize("protocol", ["ftp", "ssh", "tcp", "udp", "", "invalid"])
    def test_set_invalid_protocol(self, protocol: str) -> None:
        manager = DeviceManager()
        original = manager.current_communication_protocol
        result = manager.set_communication_protocol(protocol)
        assert "❌" in result
        assert "Invalid" in result
        assert manager.current_communication_protocol == original

    def test_set_protocol_updates_state_sequentially(self) -> None:
        manager = DeviceManager()
        manager.set_communication_protocol("dns")
        assert manager.current_communication_protocol == "dns"
        manager.set_communication_protocol("http")
        assert manager.current_communication_protocol == "http"

    def test_invalid_protocol_error_lists_allowed_values(self) -> None:
        manager = DeviceManager()
        result = manager.set_communication_protocol("ftp")
        assert "http" in result
        assert "https" in result
        assert "dns" in result


class TestDeviceManagerInitialization:
    """Tests for DeviceManager default state."""

    def test_default_beacon_interval(self) -> None:
        manager = DeviceManager()
        assert manager.current_beacon_interval == 15

    def test_default_communication_protocol(self) -> None:
        manager = DeviceManager()
        assert manager.current_communication_protocol == "https"

    def test_default_devices_not_empty(self) -> None:
        manager = DeviceManager()
        assert len(manager.devices) > 0

    def test_default_cookies_not_empty(self) -> None:
        manager = DeviceManager()
        assert len(manager.cookies) > 0

    def test_devices_are_independent_copies(self) -> None:
        """Ensure each DeviceManager instance has its own device list."""
        manager_a = DeviceManager()
        manager_b = DeviceManager()
        manager_a.devices.clear()
        assert len(manager_b.devices) > 0
