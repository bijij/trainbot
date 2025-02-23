import os

import discord

TOKEN: str | None = os.getenv("TRAIN_DISCORD_TOKEN")
if TOKEN is None:
    raise ValueError("TRAIN_DISCORD_TOKEN is not set")


client = discord.Client(intents=discord.Intents.all())



if __name__ == "__main__":
    client.run(TOKEN)
