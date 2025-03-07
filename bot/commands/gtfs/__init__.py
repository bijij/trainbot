from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

import discord
import discord.app_commands
import discord.ui

from ...gtfs.types import Direction, RouteType
from ...health import HealthStatusId
from ...mediator import ChannelNames, GetNextServicesRequest, GetNextTrainsRequest, SearchStopsRequest
from .timetable_renderer import render_timetable

if TYPE_CHECKING:
    from ...bot import TrainBot


TRANSLINK_LOGO = "https://framework.transinfo.com.au/v2.5.2.12858/images/logos/MyTL-app-icon@180.png"


TIMETABLE_GROUP = discord.app_commands.Group(
    name="timetable",
    description="Timetable commands",
)


def _autocomplete(
    route_type: RouteType, *, parent_only: bool = False
) -> Callable[[discord.Interaction[TrainBot], str], Coroutine[Any, Any, list[discord.app_commands.Choice[str]]]]:
    async def inner(interaction: discord.Interaction[TrainBot], query: str) -> list[discord.app_commands.Choice[str]]:
        if not await interaction.client.health_tracker.get_health(HealthStatusId.GTFS_AVAILABLE):
            return []

        request = SearchStopsRequest(query=query, route_type=route_type, parent_only=parent_only)
        result = await interaction.client.mediator.request(ChannelNames.GTFS, request)
        return [discord.app_commands.Choice(name=stop.name, value=stop.id) for stop in result.stops][:25]

    return inner


def _with_code_block(text: str, language: str) -> str:
    return f"```{language}\n{text}\n```"


@TIMETABLE_GROUP.command()
@discord.app_commands.describe(
    stop_id="The GTFS stop ID to retrieve the train timetable for.",
    private="Whether to send the link privately.",
)
@discord.app_commands.autocomplete(stop_id=_autocomplete(RouteType.RAIL, parent_only=True))
async def train(
    interaction: discord.Interaction[TrainBot],
    stop_id: str,
    direction: Direction,
    private: bool = False,
) -> None:
    """Retrieves the link to the train timetable for the given stop."""
    if not await interaction.client.health_tracker.get_health(HealthStatusId.GTFS_AVAILABLE):
        await interaction.response.send_message("GTFS data is currently unavailable.", ephemeral=True)
        return

    try:
        request = GetNextTrainsRequest(stop_id=stop_id, time=interaction.created_at)
        stop, down_trains, up_trains = await interaction.client.mediator.request(ChannelNames.GTFS, request)
    except Exception:
        await interaction.response.send_message("Failed to retrieve timetable.", ephemeral=True)
        raise

    now = interaction.created_at.astimezone(interaction.client.config.local_timezone)
    trains = down_trains if direction is Direction.DOWNWARD else up_trains
    lookahead_hours = interaction.client.config.lookahead_window[RouteType.RAIL]
    timetable = _with_code_block(render_timetable(stop, now, trains, RouteType.RAIL, lookahead_hours, direction), "ansi")

    await interaction.response.send_message(
        embed=discord.Embed(
            description=timetable,
            timestamp=interaction.created_at,
            color=discord.Colour.red(),
        ).set_author(
            icon_url=TRANSLINK_LOGO,
            name=f"{stop.name} Train Timetable",
            url=stop.url,
        ),
        ephemeral=private,
    )


@TIMETABLE_GROUP.command()
@discord.app_commands.describe(
    stop_id="The GTFS stop ID to retrieve the bus timetable for.",
    private="Whether to send the link privately.",
)
@discord.app_commands.autocomplete(stop_id=_autocomplete(RouteType.BUS))
async def bus(
    interaction: discord.Interaction[TrainBot],
    stop_id: str,
    private: bool = False,
) -> None:
    """Retrieves the link to the bus timetable for the given stop."""
    if not await interaction.client.health_tracker.get_health(HealthStatusId.GTFS_AVAILABLE):
        await interaction.response.send_message("GTFS data is currently unavailable.", ephemeral=True)
        return

    try:
        request = GetNextServicesRequest(stop_id=stop_id, route_type=RouteType.BUS, time=interaction.created_at)
        stop, buses = await interaction.client.mediator.request(ChannelNames.GTFS, request)
    except Exception:
        await interaction.response.send_message("Failed to retrieve timetable.", ephemeral=True)
        raise

    now = interaction.created_at.astimezone(interaction.client.config.local_timezone)
    lookahead_hours = interaction.client.config.lookahead_window[RouteType.BUS]
    timetable = _with_code_block(render_timetable(stop, now, buses, RouteType.BUS, lookahead_hours), "ansi")

    await interaction.response.send_message(
        embed=discord.Embed(
            description=timetable,
            timestamp=interaction.created_at,
            colour=discord.Colour.pink(),
        ).set_author(
            icon_url=TRANSLINK_LOGO,
            name=f"{stop.name} Bus Timetable",
            url=stop.url,
        ),
        ephemeral=private,
    )


@TIMETABLE_GROUP.command()
@discord.app_commands.describe(
    stop_id="The GTFS stop ID to retrieve the tram timetable for.",
    private="Whether to send the link privately.",
)
@discord.app_commands.autocomplete(stop_id=_autocomplete(RouteType.TRAM, parent_only=True))
async def tram(
    interaction: discord.Interaction[TrainBot],
    stop_id: str,
    private: bool = False,
) -> None:
    """Retrieves the link to the tram timetable for the given stop."""
    if not await interaction.client.health_tracker.get_health(HealthStatusId.GTFS_AVAILABLE):
        await interaction.response.send_message("GTFS data is currently unavailable.", ephemeral=True)
        return

    try:
        request = GetNextServicesRequest(stop_id=stop_id, route_type=RouteType.TRAM, time=interaction.created_at)
        stop, trams = await interaction.client.mediator.request(ChannelNames.GTFS, request)
    except Exception:
        await interaction.response.send_message("Failed to retrieve timetable.", ephemeral=True)
        raise

    now = interaction.created_at.astimezone(interaction.client.config.local_timezone)
    lookahead_hours = interaction.client.config.lookahead_window[RouteType.TRAM]
    timetable = _with_code_block(render_timetable(stop, now, trams, RouteType.TRAM, lookahead_hours), "ansi")

    await interaction.response.send_message(
        embed=discord.Embed(
            description=timetable,
            timestamp=interaction.created_at,
            color=discord.Colour.gold(),
        ).set_author(
            icon_url=TRANSLINK_LOGO,
            name=f"{stop.name} Tram Timetable",
            url=stop.url,
        ),
        ephemeral=private,
    )


@TIMETABLE_GROUP.command()
@discord.app_commands.describe(
    stop_id="The GTFS stop ID to retrieve the ferry timetable for.",
    private="Whether to send the link privately.",
)
@discord.app_commands.autocomplete(stop_id=_autocomplete(RouteType.FERRY))
async def ferry(
    interaction: discord.Interaction[TrainBot],
    stop_id: str,
    private: bool = False,
) -> None:
    """Retrieves the link to the ferry timetable for the given stop."""
    if not await interaction.client.health_tracker.get_health(HealthStatusId.GTFS_AVAILABLE):
        await interaction.response.send_message("GTFS data is currently unavailable.", ephemeral=True)
        return

    try:
        request = GetNextServicesRequest(stop_id=stop_id, route_type=RouteType.FERRY, time=interaction.created_at)
        stop, ferries = await interaction.client.mediator.request(ChannelNames.GTFS, request)
    except Exception:
        await interaction.response.send_message("Failed to retrieve timetable.", ephemeral=True)
        raise

    now = interaction.created_at.astimezone(interaction.client.config.local_timezone)
    lookahead_hours = interaction.client.config.lookahead_window[RouteType.FERRY]
    timetable = f"```ansi\n{render_timetable(stop, now, ferries, RouteType.FERRY, lookahead_hours)}\n```"

    await interaction.response.send_message(
        embed=discord.Embed(
            description=timetable,
            timestamp=interaction.created_at,
            color=discord.Colour.blue(),
        ).set_author(
            icon_url=TRANSLINK_LOGO,
            name=f"{stop.name} Ferry Timetable",
            url=stop.url,
        ),
        ephemeral=private,
    )
