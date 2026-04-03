"""Tests for the Discord bot commands and access control."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio  # noqa: F401 — ensures the plugin is loaded

import discord
from discord.ext import commands

# Ensure the project root (discord-bot/) is on sys.path.
# This allows importing config, devices, bot as top-level modules.
sys.path.insert(0, ".")

from config import ADMIN_DISCORD_ID  # noqa: E402
from bot import bot, device_manager, is_admin  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_context(
    author_id: int = ADMIN_DISCORD_ID,
    *,
    is_admin_user: bool = True,
) -> MagicMock:
    """Create a mocked discord.ext.commands.Context."""
    ctx = MagicMock(spec=commands.Context)
    ctx.author = MagicMock(spec=discord.Member)
    ctx.author.id = author_id
    ctx.send = AsyncMock()
    ctx.bot = bot
    return ctx


# ---------------------------------------------------------------------------
# Access control tests
# ---------------------------------------------------------------------------

class TestIsAdmin:
    """Tests for the is_admin check."""

    def test_admin_user_is_allowed(self) -> None:
        ctx = _make_context(author_id=ADMIN_DISCORD_ID)
        assert is_admin(ctx) is True

    def test_non_admin_user_is_denied(self) -> None:
        ctx = _make_context(author_id=999999999999999999)
        assert is_admin(ctx) is False

    def test_zero_id_is_denied(self) -> None:
        ctx = _make_context(author_id=0)
        assert is_admin(ctx) is False


# ---------------------------------------------------------------------------
# Command tests
# ---------------------------------------------------------------------------

class TestShowDevicesCommand:
    """Tests for the !show-devices command handler."""

    @pytest.mark.asyncio
    async def test_show_devices_sends_response(self) -> None:
        ctx = _make_context()
        command = bot.get_command("show-devices")
        assert command is not None
        await command.callback(ctx)  # type: ignore[arg-type]
        ctx.send.assert_called_once()
        sent_text = ctx.send.call_args[0][0]
        assert "Managed Devices" in sent_text


class TestSetBeaconIntervalCommand:
    """Tests for the !set-beacon-interval command handler."""

    @pytest.mark.asyncio
    async def test_valid_interval(self) -> None:
        ctx = _make_context()
        command = bot.get_command("set-beacon-interval")
        assert command is not None
        await command.callback(ctx, 16)  # type: ignore[arg-type]
        ctx.send.assert_called_once()
        sent_text = ctx.send.call_args[0][0]
        assert "✅" in sent_text
        assert "16" in sent_text

    @pytest.mark.asyncio
    async def test_invalid_interval(self) -> None:
        ctx = _make_context()
        command = bot.get_command("set-beacon-interval")
        assert command is not None
        await command.callback(ctx, 99)  # type: ignore[arg-type]
        ctx.send.assert_called_once()
        sent_text = ctx.send.call_args[0][0]
        assert "❌" in sent_text


class TestRequestCookiesCommand:
    """Tests for the !request-cookies command handler."""

    @pytest.mark.asyncio
    async def test_request_cookies_sends_response(self) -> None:
        ctx = _make_context()
        command = bot.get_command("request-cookies")
        assert command is not None
        await command.callback(ctx)  # type: ignore[arg-type]
        ctx.send.assert_called_once()
        sent_text = ctx.send.call_args[0][0]
        assert "Cookies" in sent_text


class TestSetCommunicationProtocolCommand:
    """Tests for the !set-communication-protocol command handler."""

    @pytest.mark.asyncio
    async def test_valid_protocol(self) -> None:
        ctx = _make_context()
        command = bot.get_command("set-communication-protocol")
        assert command is not None
        await command.callback(ctx, "dns")  # type: ignore[arg-type]
        ctx.send.assert_called_once()
        sent_text = ctx.send.call_args[0][0]
        assert "✅" in sent_text
        assert "dns" in sent_text

    @pytest.mark.asyncio
    async def test_invalid_protocol(self) -> None:
        ctx = _make_context()
        command = bot.get_command("set-communication-protocol")
        assert command is not None
        await command.callback(ctx, "ftp")  # type: ignore[arg-type]
        ctx.send.assert_called_once()
        sent_text = ctx.send.call_args[0][0]
        assert "❌" in sent_text


# ---------------------------------------------------------------------------
# Error handler tests
# ---------------------------------------------------------------------------

class TestOnCommandError:
    """Tests for the global on_command_error handler."""

    @pytest.mark.asyncio
    async def test_check_failure_sends_access_denied(self) -> None:
        ctx = _make_context()
        error = commands.CheckFailure()
        # Call the error handler directly by accessing the cog listener
        await bot.on_command_error(ctx, error)  # type: ignore[arg-type]
        ctx.send.assert_called_once()
        sent_text = ctx.send.call_args[0][0]
        assert "Access denied" in sent_text

    @pytest.mark.asyncio
    async def test_missing_required_argument(self) -> None:
        ctx = _make_context()
        # Create a mock parameter
        param = MagicMock()
        param.name = "interval"
        error = commands.MissingRequiredArgument(param)
        await bot.on_command_error(ctx, error)  # type: ignore[arg-type]
        ctx.send.assert_called_once()
        sent_text = ctx.send.call_args[0][0]
        assert "interval" in sent_text

    @pytest.mark.asyncio
    async def test_bad_argument(self) -> None:
        ctx = _make_context()
        error = commands.BadArgument("bad value")
        await bot.on_command_error(ctx, error)  # type: ignore[arg-type]
        ctx.send.assert_called_once()
        sent_text = ctx.send.call_args[0][0]
        assert "Invalid argument" in sent_text

    @pytest.mark.asyncio
    async def test_command_not_found(self) -> None:
        ctx = _make_context()
        error = commands.CommandNotFound()
        await bot.on_command_error(ctx, error)  # type: ignore[arg-type]
        ctx.send.assert_called_once()
        sent_text = ctx.send.call_args[0][0]
        assert "Unknown command" in sent_text

    @pytest.mark.asyncio
    async def test_unexpected_error_is_raised(self) -> None:
        ctx = _make_context()
        error = commands.CommandError("unexpected")
        # CommandError is the base class but not CheckFailure, BadArgument, etc.
        # Our handler should re-raise it.
        with pytest.raises(commands.CommandError):
            await bot.on_command_error(ctx, error)  # type: ignore[arg-type]
        ctx.send.assert_called_once()
