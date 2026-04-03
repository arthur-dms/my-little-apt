"""
Configuration module for the Discord bot.
All settings are hardcoded here for simplicity.
"""

# ---------------------------------------------------------------------------
# Redis connection settings (for server communication)
# ---------------------------------------------------------------------------

REDIS_HOST: str = "localhost"
REDIS_PORT: int = 6379
REDIS_DB: int = 0
REDIS_CHANNEL_COMMANDS: str = "c2:commands"
REDIS_CHANNEL_RESPONSES: str = "c2:responses"

# The Discord bot API token used to authenticate the bot with Discord.
# Replace this with your actual bot token from the Discord Developer Portal.
DISCORD_BOT_TOKEN: str = "YOUR_DISCORD_BOT_TOKEN_HERE"

# The Discord user ID of the administrator who is allowed to run commands.
# Replace this with the actual Discord user ID (numeric string).
ADMIN_DISCORD_ID: int = 123456789012345678

# The command prefix used to invoke bot commands (e.g., !show-devices).
COMMAND_PREFIX: str = "!"

# Valid beacon interval values in seconds.
VALID_BEACON_INTERVALS: list[int] = [2, 4, 8, 16, 32]

# Valid communication protocol options.
VALID_COMMUNICATION_PROTOCOLS: list[str] = ["http", "https", "dns"]
