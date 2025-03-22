import asyncio
import datetime
import logging
from zoneinfo import ZoneInfo

import aiohttp
from audino import HealthTracker
from discord.ext.tasks import loop
from malamar import Service

from ..health import HealthStatusId
from .proto import FeedMessage, TripUpdate
from .store import GtfsDataStore

TRIP_UPDATE_URL = "https://gtfsrt.api.translink.com.au/api/realtime/SEQ/TripUpdates"

REFRESH_INTERVAL = 30

CANCELLED_TRIP_SCHEDULE_RELATIONSHIP = 3
SKIPPED_STOP_SCHEDULE_RELATIONSHIP = 1

BRISBANE = ZoneInfo("Australia/Brisbane")

_log = logging.getLogger(__name__)


class RealtimeGtfsHandler(Service):
    """A service that handles GTFS realtime data."""

    def __init__(
        self,
        health_tracker: HealthTracker,
        data_store: GtfsDataStore,
    ) -> None:
        """Initializes the GTFS realtime handler."

        Parameters
        ----------
        health_tracker : HealthTracker
            The health tracker to use for tracking the health of the service.
        data_store : GtfsDataStore
            The GTFS data store to use for data retrieval and updating.
        """
        self._lock = asyncio.Lock()
        self._health_tracker = health_tracker
        self._data_store = data_store
        self._static_available: bool = False
        super().__init__()

        self._update_gtfs_realtime_data.add_exception_type(aiohttp.ClientError)

    async def _process_trip_update(self, trip_update: TripUpdate, deleted: bool = True) -> None:
        """Process a trip update from the GTFS realtime feed.

        Parameters
        ----------
        trip_update : TripUpdate
            The trip update to process.
        deleted : bool
            Whether the trip update is a deletion.
        """
        if trip_update.trip.trip_id is None:
            return  # We can't handle trip updates without a trip ID at the moment
        if trip_update.trip.start_date is None:
            return  # We can't handle trip updates without a start date at the moment

        # Parse the start date
        start_date = datetime.datetime.strptime(trip_update.trip.start_date, "%Y%m%d").date()

        if deleted:
            self._data_store.reset_realtime_data(trip_update.trip.trip_id, start_date)
            return

        # Update the cancellation status of the trip instance
        cancelled = trip_update.trip.schedule_relationship == CANCELLED_TRIP_SCHEDULE_RELATIONSHIP
        self._data_store.set_trip_instance_status(trip_update.trip.trip_id, start_date, cancelled)

        # Update the actual arrival and departure times of the stop times
        for stop_time_update in trip_update.stop_time_update:
            if stop_time_update.stop_id is None:
                continue
            if stop_time_update.stop_sequence is None:
                continue

            skipped = stop_time_update.schedule_relationship == SKIPPED_STOP_SCHEDULE_RELATIONSHIP
            self._data_store.set_stop_time_instance_status(trip_update.trip.trip_id, start_date, stop_time_update.stop_sequence, skipped)

            if stop_time_update.arrival is not None and stop_time_update.arrival.time is not None:
                arrival_time = datetime.datetime.fromtimestamp(stop_time_update.arrival.time, datetime.timezone.utc).astimezone(BRISBANE)
                self._data_store.set_stop_time_actual_arrival_time(
                    trip_update.trip.trip_id, start_date, stop_time_update.stop_sequence, arrival_time
                )

            if stop_time_update.departure is not None and stop_time_update.departure.time is not None:
                departure_time = datetime.datetime.fromtimestamp(stop_time_update.departure.time, datetime.timezone.utc).astimezone(BRISBANE)
                self._data_store.set_stop_time_actual_departure_time(
                    trip_update.trip.trip_id, start_date, stop_time_update.stop_sequence, departure_time
                )

    @loop(seconds=REFRESH_INTERVAL)
    async def _update_gtfs_realtime_data(self) -> None:
        async with self._lock:
            if self._static_available:
                async with aiohttp.ClientSession() as session:
                    async with session.get(TRIP_UPDATE_URL) as response:
                        feed_message = FeedMessage()
                        feed_message.ParseFromString(await response.read())

                for entity in feed_message.entity:
                    if entity.trip_update:
                        try:
                            await self._process_trip_update(entity.trip_update, entity.is_deleted or False)
                        except Exception:
                            # _log.debug("Failed to process trip update")
                            pass

    async def _handle_health_update(self, health_status_id: str, healthy: bool) -> None:
        async with self._lock:
            if health_status_id == HealthStatusId.GTFS_AVAILABLE:
                if not healthy:
                    self._static_available = False
                elif healthy and not self._static_available:
                    self._static_available = True

    async def start(self, *, timeout: float | None = None) -> None:
        """Starts the GTFS realtime handler.

        Paramters
        ----------
        timeout : float | None
            The maximum time to wait for the service to start.
        """
        self._health_tracker.subscribe(self._handle_health_update)
        self._update_gtfs_realtime_data.start()

    async def stop(self, *, timeout: float | None = None) -> None:
        """Stops the GTFS realtime handler.

        Paramters
        ----------
        timeout : float | None
            The maximum time to wait for the service to stop.
        """
        self._update_gtfs_realtime_data.stop()
