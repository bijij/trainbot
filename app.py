import asyncio

from audino import HealthTracker
from malamar import Application
from rayquaza import Mediator

from bot.communication.bot import Bot
from bot.configuration import BotConfiguration
from bot.model.gtfs import GtfsDataStore, GtfsProvider, RealtimeGtfsHandler, StaticGtfsHandler

mediator = Mediator()
health_tracker = HealthTracker(mediator=mediator)

app = Application()

app.add_singleton(BotConfiguration)

app.add_singleton(mediator, type=Mediator)
app.add_singleton(health_tracker, type=HealthTracker)
app.add_singleton(GtfsDataStore)

app.add_service(StaticGtfsHandler)
app.add_service(RealtimeGtfsHandler)
app.add_service(GtfsProvider)
app.add_service(Bot)

if __name__ == "__main__":
    asyncio.run(app.run())
