"""Tests for the config module."""

from config import (
    ADMIN_DISCORD_ID,
    COMMAND_PREFIX,
    DISCORD_BOT_TOKEN,
    VALID_BEACON_INTERVALS,
    VALID_COMMUNICATION_PROTOCOLS,
)


class TestConfigConstants:
    """Verify that all configuration constants are defined with the correct types."""

    def test_bot_token_is_string(self) -> None:
        assert isinstance(DISCORD_BOT_TOKEN, str)

    def test_bot_token_is_not_empty(self) -> None:
        assert len(DISCORD_BOT_TOKEN) > 0

    def test_admin_id_is_integer(self) -> None:
        assert isinstance(ADMIN_DISCORD_ID, int)

    def test_admin_id_is_positive(self) -> None:
        assert ADMIN_DISCORD_ID > 0

    def test_command_prefix_is_string(self) -> None:
        assert isinstance(COMMAND_PREFIX, str)

    def test_command_prefix_is_not_empty(self) -> None:
        assert len(COMMAND_PREFIX) > 0

    def test_valid_beacon_intervals_is_list(self) -> None:
        assert isinstance(VALID_BEACON_INTERVALS, list)

    def test_valid_beacon_intervals_contains_expected_values(self) -> None:
        assert VALID_BEACON_INTERVALS == [2, 8, 16, 32]

    def test_valid_beacon_intervals_all_integers(self) -> None:
        assert all(isinstance(v, int) for v in VALID_BEACON_INTERVALS)

    def test_valid_communication_protocols_is_list(self) -> None:
        assert isinstance(VALID_COMMUNICATION_PROTOCOLS, list)

    def test_valid_communication_protocols_contains_expected_values(self) -> None:
        assert VALID_COMMUNICATION_PROTOCOLS == ["http", "https", "dns"]

    def test_valid_communication_protocols_all_strings(self) -> None:
        assert all(isinstance(v, str) for v in VALID_COMMUNICATION_PROTOCOLS)
