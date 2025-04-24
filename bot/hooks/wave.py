from __future__ import annotations

import re
from typing import TYPE_CHECKING

import discord

from ..configuration import Configuration
from .hook import Hook

if TYPE_CHECKING:
    from ..bot import TrainBot

MATCHES = [
    re.compile(r"(?:^|\s)DSCL?(?:$|\s)", re.IGNORECASE),
    re.compile(r"(?:^|\s)Direct Sunshine Coast(?:$|\s)", re.IGNORECASE),
    re.compile(r"(?:^|\s)CAMCOS(?:$|\s)", re.IGNORECASE),
]

WAVE_PAGE = "https://www.delivering2032.com.au/legacy-for-queensland/transport"


class Wave(Hook):
    event = "message"

    def __init__(self, config: Configuration) -> None:
        self.config = config

    async def callback(self, _: TrainBot, message: discord.Message) -> None:
        if message.guild is None or message.guild.id != self.config.transit_server_id:
            return

        if message.author.bot:
            return

        for regex in MATCHES:
            if regex.search(message.content):
                await message.channel.send(f"🌊 [Ride the wave bro!](<{WAVE_PAGE}>) 🌊", reference=message.reference or message)
                break
