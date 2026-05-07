"""
Configuration module for the C2 server.
All settings are hardcoded here for simplicity.
Copy this file to config.py and adjust values as needed.
"""

# ---------------------------------------------------------------------------
# HTTP server settings
# ---------------------------------------------------------------------------

SERVER_HOST: str = "0.0.0.0"  # nosec B104 — intentional: server must accept external connections
SERVER_PORT: int = 8000

# ---------------------------------------------------------------------------
# C2 operational parameters
# ---------------------------------------------------------------------------

# Valid beacon interval values in seconds.
VALID_BEACON_INTERVALS: list[int] = [15, 30, 60, 120]

# Valid communication protocol options.
VALID_COMMUNICATION_PROTOCOLS: list[str] = ["http", "https", "dns"]

# ---------------------------------------------------------------------------
# Encryption (HTTPS protocol mode)
# ---------------------------------------------------------------------------

# AES-256 shared key (must be exactly 32 bytes).
# MUST match the AES_KEY constant in trojan-impl/C2NetworkModule.kt.
AES_SECRET_KEY: str = "c2k3y1234567890cabcdef1234567890"

# ---------------------------------------------------------------------------
# DNS exfiltration listener
# ---------------------------------------------------------------------------

# UDP port for the DNS exfiltration listener.
# Default 5300 avoids needing root. Use 53 for a realistic setup (requires sudo
# or: sudo setcap 'cap_net_bind_service=+ep' $(which python3)).
DNS_LISTENER_PORT: int = 5300
