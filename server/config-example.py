"""
Configuration module for the C2 server.
All settings are hardcoded here for simplicity.
Copy this file to config.py and adjust values as needed.
"""

# ---------------------------------------------------------------------------
# HTTP server settings
# ---------------------------------------------------------------------------

SERVER_HOST: str = "0.0.0.0"
SERVER_PORT: int = 8000

# ---------------------------------------------------------------------------
# C2 operational parameters
# ---------------------------------------------------------------------------

# Valid beacon interval values in seconds.
VALID_BEACON_INTERVALS: list[int] = [2, 4, 8, 16, 32]

# Valid communication protocol options.
VALID_COMMUNICATION_PROTOCOLS: list[str] = ["http", "https", "dns"]
