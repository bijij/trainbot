import asyncio
import datetime
import logging

import aiohttp
from audino import HealthTracker
from discord.ext.tasks import loop
from malamar import Service

from ...health import HealthStatusId
from .proto.types import FeedMessage, TripUpdate
from .store import GtfsDataStore

TRIP_UPDATE_URL = "https://gtfsrt.api.translink.com.au/api/realtime/SEQ/TripUpdates"

REFRESH_INTERVAL = 30

CANCELLED_TRIP_SCHEDULE_RELATIONSHIP = 3
SKIPPED_STOP_SCHEDULE_RELATIONSHIP = 1

_log = logging.getLogger(__name__)


class RealtimeGtfsHandler(Service):

    def __init__(self, health_tracker: HealthTracker, data_store: GtfsDataStore) -> None:
        self._lock = asyncio.Lock()
        self._health_tracker = health_tracker
        self._data_store = data_store
        self._static_available: bool = False
        super().__init__()

        self.update_gtfs_realtime_data.add_exception_type(aiohttp.ClientError)

    async def handle_trip_update(self, trip_update: TripUpdate) -> None:
        if trip_update.trip.trip_id is None:
            return  # We can't handle trip updates without a trip ID at the moment
        if trip_update.trip.start_date is None:
            return  # We can't handle trip updates without a start date at the moment

        # Parse the start date
        start_date = datetime.datetime.strptime(trip_update.trip.start_date, "%Y%m%d").date()

        # Update the cancellation status of the trip instance
        cancelled = trip_update.trip.schedule_relationship == CANCELLED_TRIP_SCHEDULE_RELATIONSHIP
        await self._data_store.set_trip_instance_status(trip_update.trip.trip_id, start_date, cancelled)

        # Update the actual arrival and departure times of the stop times
        for stop_time_update in trip_update.stop_time_update:
            if stop_time_update.stop_id is None:
                continue
            if stop_time_update.stop_sequence is None:
                continue

            skipped = stop_time_update.schedule_relationship == SKIPPED_STOP_SCHEDULE_RELATIONSHIP
            await self._data_store.set_stop_time_instance_status(
                trip_update.trip.trip_id, start_date, stop_time_update.stop_sequence, skipped
            )

            if stop_time_update.arrival is not None and stop_time_update.arrival.time is not None:
                arrival_time = datetime.datetime.fromtimestamp(stop_time_update.arrival.time, datetime.timezone.utc)
                await self._data_store.set_stop_time_actual_arrival_time(
                    trip_update.trip.trip_id, start_date, stop_time_update.stop_sequence, arrival_time
                )

            if stop_time_update.departure is not None and stop_time_update.departure.time is not None:
                departure_time = datetime.datetime.fromtimestamp(stop_time_update.departure.time, datetime.timezone.utc)
                await self._data_store.set_stop_time_actual_departure_time(
                    trip_update.trip.trip_id, start_date, stop_time_update.stop_sequence, departure_time
                )

    @loop(seconds=REFRESH_INTERVAL)
    async def update_gtfs_realtime_data(self) -> None:
        async with self._lock:
            if self._static_available:
                async with aiohttp.ClientSession() as session:
                    async with session.get(TRIP_UPDATE_URL) as response:
                        feed_message = FeedMessage()
                        feed_message.ParseFromString(await response.read())

                for entity in feed_message.entity:
                    if entity.trip_update:
                        try:
                            await self.handle_trip_update(entity.trip_update)
                        except Exception:
                            _log.exception("Failed to handle trip update")

    async def handle_health_update(self, health_status_id: str, healthy: bool) -> None:
        async with self._lock:
            if health_status_id == HealthStatusId.GTFS_AVAILABLE:
                if not healthy:
                    self._static_available = False
                elif healthy and not self._static_available:
                    self._static_available = True

    async def start(self, *, timeout: float | None = None) -> None:
        self._health_tracker.subscribe(self.handle_health_update)
        self.update_gtfs_realtime_data.start()

    async def stop(self, *, timeout: float | None = None) -> None:
        self.update_gtfs_realtime_data.stop()
