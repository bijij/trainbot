from hashlib import md5
from json import dumps

import discord
import discord.app_commands
import discord.ui
from audino import HealthTracker
from malamar import Application, Service
from rayquaza import Mediator

from ..configuration import BotConfiguration
from ..health import HealthStatusId
from ..mediator import ChannelNames, GetNextServicesRequest, GetNextTrainsRequest, SearchStopsRequest
from ..model.gtfs import Direction, RouteType
from .timetable_renderer import render_timetable

TRANSLINK_LOGO = "https://framework.transinfo.com.au/v2.5.2.12858/images/logos/MyTL-app-icon@180.png"


def _get_commands_hash(command_tree: discord.app_commands.CommandTree) -> int:
    """Generate a hashcode for the command tree."""
    assert command_tree.client.user is not None
    hashcode = command_tree.client.user.id

    for command in command_tree.walk_commands():
        data = dumps(command.to_dict(command_tree)).encode("utf-8")
        hashcode = (hashcode * 397) ^ int.from_bytes(md5(data).digest())

    for context_menu in command_tree.walk_commands(type=discord.AppCommandType.message):
        data = dumps(context_menu.to_dict(command_tree)).encode("utf-8")
        hashcode = (hashcode * 397) ^ int.from_bytes(md5(data).digest())

    for context_menu in command_tree.walk_commands(type=discord.AppCommandType.user):
        data = dumps(context_menu.to_dict(command_tree)).encode("utf-8")
        hashcode = (hashcode * 397) ^ int.from_bytes(md5(data).digest())

    return hashcode


class TrainBot(discord.Client):
    app: Application
    config: BotConfiguration
    health_tracker: HealthTracker
    mediator: Mediator
    command_tree: discord.app_commands.CommandTree

    async def setup_hook(self) -> None:
        new_hash = _get_commands_hash(self.command_tree)
        if self.config.command_hash != new_hash:
            print("Detected command changes, syncing...")
            await self.command_tree.sync()
            self.config.command_hash = new_hash

    async def on_ready(self) -> None:
        assert self.user is not None
        print(f"Logged in as {self.user} ({self.user.id})")

    async def on_disconnect(self) -> None: ...


TRAIN_BOT = TrainBot(intents=discord.Intents.default())


TRAIN_BOT_COMMANDS = discord.app_commands.CommandTree(
    TRAIN_BOT,
    allowed_contexts=discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
    allowed_installs=discord.app_commands.installs.AppInstallationType(guild=True, user=True),
)


TIMETABLE_GROUP = discord.app_commands.Group(
    name="timetable",
    description="Timetable commands",
)
TRAIN_BOT_COMMANDS.add_command(TIMETABLE_GROUP)


@TIMETABLE_GROUP.command()
@discord.app_commands.describe(
    stop_id="The GTFS stop ID to retrieve the train timetable for.",
    private="Whether to send the link privately.",
)
async def train(interaction: discord.Interaction, stop_id: str, direction: Direction, private: bool = False) -> None:
    """Retrieves the link to the train timetable for the given stop."""
    assert isinstance(interaction.client, TrainBot)

    if not await interaction.client.health_tracker.get_health(HealthStatusId.GTFS_AVAILABLE):
        await interaction.response.send_message("GTFS data is currently unavailable.", ephemeral=True)
        return

    try:
        request = GetNextTrainsRequest(stop_id=stop_id)
        stop, down_trains, up_trains = await interaction.client.mediator.request(ChannelNames.GTFS, request)
    except Exception as e:
        print(e)
        await interaction.response.send_message("Failed to retrieve timetable.", ephemeral=True)
        return

    timetable = f"```ansi\n{render_timetable(stop, interaction.created_at, down_trains if direction is Direction.DOWNWARD else up_trains, RouteType.RAIL, direction)}\n```"

    await interaction.response.send_message(
        embed=discord.Embed(description=timetable, timestamp=interaction.created_at).set_author(
            icon_url=TRANSLINK_LOGO, name=f"{stop.name} Train Timetable"
        ),
        ephemeral=private,
    )


@train.autocomplete("stop_id")
async def _train_autocomplete_stop_id(interaction: discord.Interaction, query: str) -> list[discord.app_commands.Choice[str]]:
    assert isinstance(interaction.client, TrainBot)

    if not await interaction.client.health_tracker.get_health(HealthStatusId.GTFS_AVAILABLE):
        return []

    result = await interaction.client.mediator.request(ChannelNames.GTFS, SearchStopsRequest(query=query, route_type=RouteType.RAIL))
    return [discord.app_commands.Choice(name=stop.name, value=stop.id) for stop in result.stops]


@TIMETABLE_GROUP.command()
@discord.app_commands.describe(
    stop_id="The GTFS stop ID to retrieve the bus timetable for.",
    private="Whether to send the link privately.",
)
async def bus(interaction: discord.Interaction, stop_id: str, private: bool = False) -> None:
    """Retrieves the link to the bus timetable for the given stop."""
    assert isinstance(interaction.client, TrainBot)

    if not await interaction.client.health_tracker.get_health(HealthStatusId.GTFS_AVAILABLE):
        await interaction.response.send_message("GTFS data is currently unavailable.", ephemeral=True)
        return

    try:
        request = GetNextServicesRequest(stop_id=stop_id, route_type=RouteType.BUS)
        stop, buses = await interaction.client.mediator.request(ChannelNames.GTFS, request)
    except Exception as e:
        print(e)
        await interaction.response.send_message("Failed to retrieve timetable.", ephemeral=True)
        return

    timetable = f"```ansi\n{render_timetable(stop, interaction.created_at, buses, RouteType.BUS)}\n```"

    await interaction.response.send_message(
        embed=discord.Embed(description=timetable, timestamp=interaction.created_at).set_author(
            icon_url=TRANSLINK_LOGO, name=f"{stop.name} Bus Timetable"
        ),
        ephemeral=private,
    )


@bus.autocomplete("stop_id")
async def _bus_autocomplete_stop_id(interaction: discord.Interaction, query: str) -> list[discord.app_commands.Choice[str]]:
    assert isinstance(interaction.client, TrainBot)

    if not await interaction.client.health_tracker.get_health(HealthStatusId.GTFS_AVAILABLE):
        return []

    result = await interaction.client.mediator.request(ChannelNames.GTFS, SearchStopsRequest(query=query, route_type=RouteType.BUS))
    return [discord.app_commands.Choice(name=stop.name, value=stop.id) for stop in result.stops]


class Bot(Service):

    def __init__(
        self,
        *,
        app: Application,
        config: BotConfiguration,
        health_tracker: HealthTracker,
        mediator: Mediator,
    ) -> None:
        TRAIN_BOT.app = app
        TRAIN_BOT.config = config
        TRAIN_BOT.health_tracker = health_tracker
        TRAIN_BOT.mediator = mediator
        TRAIN_BOT.command_tree = TRAIN_BOT_COMMANDS

        discord.utils.setup_logging()

        super().__init__()

    async def start(self, *, timeout: float | None = None) -> None:
        await TRAIN_BOT.__aenter__()
        TRAIN_BOT.loop.create_task(TRAIN_BOT.start(TRAIN_BOT.config.token))

    async def stop(self, *, timeout: float | None = None) -> None:
        await TRAIN_BOT.__aexit__(None, None, None)
