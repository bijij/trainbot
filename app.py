import asyncio

from audino import HealthTracker
from malamar import Application
from rayquaza import Mediator

from bot.bot import Commands, TrainBot
from bot.commands import ALL_COMMANDS
from bot.configuration import Configuration
from bot.gtfs import GtfsDataStore, GtfsProvider, RealtimeGtfsHandler, StaticGtfsHandler

mediator = Mediator()
health_tracker = HealthTracker(mediator=mediator)

app = Application()

app.add_singleton(Configuration)

app.add_singleton(mediator, type=Mediator)
app.add_singleton(health_tracker, type=HealthTracker)
app.add_singleton(GtfsDataStore)

app.add_service(StaticGtfsHandler)
app.add_service(RealtimeGtfsHandler)
app.add_service(GtfsProvider)

for command in ALL_COMMANDS:
    app.add_singleton(command, type=Commands)

app.add_service(TrainBot)

if __name__ == "__main__":
    asyncio.run(app.run())
