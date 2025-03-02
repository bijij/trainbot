import asyncio

from audino import HealthTracker
from malamar import Application
from rayquaza import Mediator

from bot.configuration import BotConfiguration
from bot.communication.bot import Bot
from bot.model.db import Database
from bot.model.gtfs import Gtfs

mediator = Mediator()
health_tracker = HealthTracker(mediator=mediator)

app = Application()

app.add_singleton(BotConfiguration)

app.add_singleton(mediator, type=Mediator)
app.add_singleton(health_tracker, type=HealthTracker)
app.add_singleton(Database)

app.add_service(Gtfs)
app.add_service(Bot)

if __name__ == "__main__":
    asyncio.run(app.run())
