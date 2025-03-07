from __future__ import annotations

from collections import defaultdict
from datetime import tzinfo
from os import environ
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from ..gtfs.types import RouteType


class Configuration:
    """Configuration items required by services."""

    @property
    def token(self) -> str:
        """str: The Discord bot token."""
        token = environ.get("TRAIN_DISCORD_TOKEN")
        if token is None:
            raise ValueError("Discord token not found in environment variables.")
        return token

    @property
    def command_hash(self) -> int:
        """int: The hashcode of the bot's application commands."""
        try:
            with open("config/command_hash", "r") as f:
                return int(f.read())
        except Exception:
            return 0

    @command_hash.setter
    def command_hash(self, value: int) -> None:
        try:
            with open("config/command_hash", "w") as f:
                f.write(str(value))
        except Exception:
            pass

    @property
    def local_timezone(self) -> tzinfo:
        """tzinfo: The local timezone."""
        return ZoneInfo("Australia/Brisbane")

    @property
    def lookahead_window(self) -> dict[RouteType, int]:
        """dict[RouteType, int]: The lookahead window for each route type."""
        from ..gtfs.types import RouteType  # This is to avoid a circular import.

        return defaultdict(lambda: 8) | {
            RouteType.RAIL: 4,
            RouteType.TRAM: 2,
        }

    @property
    def max_results(self) -> dict[RouteType, int]:
        """dict[RouteType, int]: The maximum number of results to return for each route type."""
        from ..gtfs.types import RouteType  # This is to avoid a circular import.

        return defaultdict(lambda: 10) | {
            RouteType.RAIL: 6,
            RouteType.TRAM: 2,
        }
