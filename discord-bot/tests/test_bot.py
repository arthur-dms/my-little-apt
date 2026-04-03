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
# Slash command tests — admin user
# ---------------------------------------------------------------------------

class TestShowDevicesCommand:
    """Tests for the /show-devices slash command."""

    @pytest.mark.asyncio
    async def test_admin_gets_response(self) -> None:
        interaction = _make_interaction()
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


class TestSetBeaconIntervalCommand:
    """Tests for the /set-beacon-interval slash command."""

    @pytest.mark.asyncio
    async def test_valid_interval(self) -> None:
        interaction = _make_interaction()
        await set_beacon_interval(interaction, 16)
        sent_text = interaction.response.send_message.call_args[0][0]
        assert "✅" in sent_text
        assert "16" in sent_text

    @pytest.mark.asyncio
    async def test_invalid_interval(self) -> None:
        interaction = _make_interaction()
        await set_beacon_interval(interaction, 99)
        sent_text = interaction.response.send_message.call_args[0][0]
        assert "❌" in sent_text

    @pytest.mark.asyncio
    async def test_non_admin_gets_denied(self) -> None:
        interaction = _make_interaction(author_id=999)
        await set_beacon_interval(interaction, 16)
        sent_text = interaction.response.send_message.call_args[0][0]
        assert "Access denied" in sent_text


class TestRequestCookiesCommand:
    """Tests for the /request-cookies slash command."""

    @pytest.mark.asyncio
    async def test_admin_gets_cookies(self) -> None:
        interaction = _make_interaction()
        await request_cookies(interaction)
        sent_text = interaction.response.send_message.call_args[0][0]
        assert "Cookies" in sent_text

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
        await set_communication_protocol(interaction, "dns")
        sent_text = interaction.response.send_message.call_args[0][0]
        assert "✅" in sent_text
        assert "dns" in sent_text

    @pytest.mark.asyncio
    async def test_invalid_protocol(self) -> None:
        interaction = _make_interaction()
        await set_communication_protocol(interaction, "ftp")
        sent_text = interaction.response.send_message.call_args[0][0]
        assert "❌" in sent_text

    @pytest.mark.asyncio
    async def test_non_admin_gets_denied(self) -> None:
        interaction = _make_interaction(author_id=999)
        await set_communication_protocol(interaction, "dns")
        sent_text = interaction.response.send_message.call_args[0][0]
        assert "Access denied" in sent_text


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
        assert 16 in values
        assert 2 not in values

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
