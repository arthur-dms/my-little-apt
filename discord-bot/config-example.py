"""
Configuration module for the Discord bot.
All settings are hardcoded here for simplicity.
"""

# ---------------------------------------------------------------------------
# C2 Server connection
# ---------------------------------------------------------------------------

# URL of the C2 server. When both run on the same machine, use localhost.
C2_SERVER_URL: str = "http://localhost:8000"

# The Discord bot API token used to authenticate the bot with Discord.
# Replace this with your actual bot token from the Discord Developer Portal.
DISCORD_BOT_TOKEN: str = "YOUR_DISCORD_BOT_TOKEN_HERE"

# The Discord user ID of the administrator who is allowed to run commands.
# Replace this with the actual Discord user ID (numeric string).
ADMIN_DISCORD_ID: int = 123456789012345678

# The command prefix used to invoke bot commands (e.g., !show-devices).
COMMAND_PREFIX: str = "!"

# Valid beacon interval values in seconds.
VALID_BEACON_INTERVALS: list[int] = [15, 30, 60, 120]

# Valid communication protocol options.
VALID_COMMUNICATION_PROTOCOLS: list[str] = ["http", "https", "dns"]
