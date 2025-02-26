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
from ..mediator import ChannelNames, GetStopUrlRequest, SearchStopsRequest


def _get_commands_hash(command_tree: discord.app_commands.CommandTree) -> int:
    """Generate a hashcode for the command tree."""
    assert command_tree.client.user is not None
    hashcode = command_tree.client.user.id

    for command in command_tree.walk_commands():
        data = dumps(command.to_dict(command_tree)).encode('utf-8')
        hashcode = (hashcode * 397) ^ int.from_bytes(md5(data).digest())

    for context_menu in command_tree.walk_commands(type=discord.AppCommandType.message):
        data = dumps(context_menu.to_dict(command_tree)).encode('utf-8')
        hashcode = (hashcode * 397) ^ int.from_bytes(md5(data).digest())

    for context_menu in command_tree.walk_commands(type=discord.AppCommandType.user):
        data = dumps(context_menu.to_dict(command_tree)).encode('utf-8')
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
            print('Detected command changes, syncing...')
            await self.command_tree.sync()
            self.config.command_hash = new_hash

    async def on_ready(self) -> None:
        assert self.user is not None
        print(f'Logged in as {self.user} ({self.user.id})')

    async def on_disconnect(self) -> None:
        ...


TRAIN_BOT = TrainBot(intents=discord.Intents.default())


TRAIN_BOT_COMMANDS = discord.app_commands.CommandTree(TRAIN_BOT)


@TRAIN_BOT_COMMANDS.command()
@discord.app_commands.describe(stop_id='The GTFS stop ID to retrieve the timetable for.',
                               private='Whether to send the link privately.')
async def timetable(interaction: discord.Interaction, stop_id: str, private: bool = True) -> None:
    """Retrieves the link to the timetable for the given stop."""
    assert isinstance(interaction.client, TrainBot)

    if not await interaction.client.health_tracker.get_health(HealthStatusId.GTFS_AVAILABLE):
        await interaction.response.send_message('GTFS data is currently unavailable.', ephemeral=True)
        return
    
    try:
        url = await interaction.client.mediator.request(ChannelNames.GTFS, GetStopUrlRequest(stop_id=stop_id))
    except Exception:
        await interaction.response.send_message('Failed to retrieve timetable.', ephemeral=True)
        return
    
    await interaction.response.send_message(url, ephemeral=private)


@timetable.autocomplete('stop_id')
async def _autocomplete_stop_id(interaction: discord.Interaction, query: str) -> list[discord.app_commands.Choice[str]]:
    assert isinstance(interaction.client, TrainBot)
    
    if not await interaction.client.health_tracker.get_health(HealthStatusId.GTFS_AVAILABLE):
        return []

    result = await interaction.client.mediator.request(ChannelNames.GTFS, SearchStopsRequest(query=query))
    return [discord.app_commands.Choice(name=name, value=stop_id) for stop_id, name in result.stops.items()]


class Bot(Service):

    def __init__(self, *,
                 app: Application,
                 config: BotConfiguration,
                 health_tracker: HealthTracker,
                 mediator: Mediator) -> None:
        TRAIN_BOT.app = app
        TRAIN_BOT.config = config
        TRAIN_BOT.health_tracker = health_tracker
        TRAIN_BOT.mediator = mediator
        TRAIN_BOT.command_tree = TRAIN_BOT_COMMANDS

        super().__init__()

    async def start(self, *, timeout: float | None = None) -> None:
        await TRAIN_BOT.__aenter__()
        TRAIN_BOT.loop.create_task(TRAIN_BOT.start(TRAIN_BOT.config.token))

    async def stop(self, *, timeout: float | None = None) -> None:
        await TRAIN_BOT.__aexit__(None, None, None)
