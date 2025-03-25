import asyncio
import logging
from collections import defaultdict
from hashlib import md5
from json import dumps
from typing import TYPE_CHECKING, Any, Awaitable, Callable

import discord
import discord.app_commands
import discord.ext
import discord.ext.commands
from audino import HealthTracker
from malamar import Application, Service
from rayquaza import Mediator

from .configuration import Configuration
from .hooks import Hook

_log = logging.getLogger(__name__)


Commands = discord.app_commands.Command | discord.app_commands.ContextMenu | discord.app_commands.Group


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


class TrainBot(discord.Client, Service):

    def __init__(
        self,
        *,
        app: Application,
        config: Configuration,
        health_tracker: HealthTracker,
        mediator: Mediator,
        commands: list[Commands],
        hooks: list[Hook],
    ) -> None:

        self.app: Application = app
        self.config: Configuration = config
        self.health_tracker: HealthTracker = health_tracker
        self.mediator: Mediator = mediator

        discord.Client.__init__(self, intents=discord.Intents.all())
        Service.__init__(self)

        self.command_tree = discord.app_commands.CommandTree(
            self,
            allowed_contexts=discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
            allowed_installs=discord.app_commands.installs.AppInstallationType(guild=True, user=True),
        )

        self._event_hooks = defaultdict(list)

        for hook in hooks:
            self.add_hook(hook.callback, hook.event)

        for command in commands:
            self.command_tree.add_command(command)

        discord.ext.commands.Bot

        discord.utils.setup_logging()

    def add_hook(self, func: Callable[..., Awaitable[Any]], /, name: str) -> None:
        if not asyncio.iscoroutinefunction(func):
            raise TypeError("Listeners must be coroutines")
        self._event_hooks[name].append(func)

    def dispatch(self, event: str, /, *args: Any, **kwargs: Any) -> None:
        super().dispatch(event, *args, **kwargs)
        for hook in self._event_hooks[event]:
            self._schedule_event(hook, "on_" + event, self, *args, **kwargs)  # type: ignore

    async def setup_hook(self) -> None:
        new_hash = _get_commands_hash(self.command_tree)
        if self.config.command_hash != new_hash:
            _log.info("Detected command changes, syncing...")
            await self.command_tree.sync()
            self.config.command_hash = new_hash

    async def on_ready(self) -> None:
        assert self.user is not None
        _log.info(f"Logged in as {self.user} ({self.user.id})")

    async def start(self, *, timeout: float | None = None) -> None:  # type: ignore
        await discord.Client.__aenter__(self)
        self.loop.create_task(discord.Client.start(self, self.config.token))

    async def stop(self, *, timeout: float | None = None) -> None:
        _log.info("Stopping bot...")
        await discord.Client.__aexit__(self, None, None, None)
