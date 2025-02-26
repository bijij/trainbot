from hashlib import md5
from json import dumps

import discord
import discord.app_commands
import discord.ui
from malamar import Application, Service

from ..configuration import BotConfiguration


def _get_commands_hash(command_tree: discord.app_commands.CommandTree) -> int:
    """Generate a hashcode for the command tree."""
    hashcode = 0

    for command in command_tree.walk_commands():
        data = dumps(command.to_dict(command_tree)).encode('utf-8')
        hashcode = (hashcode * 397) ^ int.from_bytes(md5(data).digest())

    return hashcode


class TrainBot(discord.Client): 
    app: Application
    config: BotConfiguration
    command_tree: discord.app_commands.CommandTree

    async def setup_hook(self) -> None:
        if self.config.command_hash != _get_commands_hash(self.command_tree):
            await self.command_tree.sync()

    async def on_ready(self) -> None:
        assert self.user is not None
        print(f'Logged in as {self.user} ({self.user.id})')

    async def on_disconnect(self) -> None:
        ...


TRAIN_BOT = TrainBot(intents=discord.Intents.default())


TRAIN_BOT_COMMANDS = discord.app_commands.CommandTree(TRAIN_BOT)


@TRAIN_BOT_COMMANDS.context_menu()
async def bonk(interaction: discord.Interaction, user: discord.User) -> None:
    await interaction.response.send_message(f'Bonked {user.mention}!', ephemeral=True)


class Bot(Service):

    def __init__(self, *, app: Application, config: BotConfiguration) -> None:
        TRAIN_BOT.app = app
        TRAIN_BOT.config = config
        TRAIN_BOT.command_tree = TRAIN_BOT_COMMANDS

        super().__init__()

    async def start(self, *, timeout: float | None = None) -> None:
        await TRAIN_BOT.__aenter__()
        TRAIN_BOT.loop.create_task(TRAIN_BOT.start(TRAIN_BOT.config.token))

    async def stop(self, *, timeout: float | None = None) -> None:
        await TRAIN_BOT.__aexit__(None, None, None)
