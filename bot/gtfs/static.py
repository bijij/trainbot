import asyncio
import csv
import datetime
import logging
from collections.abc import Callable, Mapping
from io import BytesIO, TextIOWrapper
from typing import Any
from zipfile import ZipFile

import aiohttp
from audino import HealthTracker
from discord.ext.tasks import loop
from malamar import Service as MalamarService

from ..configuration import Configuration
from ..health import HealthStatusId
from .store import GtfsDataStore
from .types import CalendarData, CalendarDateData, RouteData, StopData, StopTimeData, TripData

__all__ = ("StaticGtfsHandler",)


_log = logging.getLogger(__name__)


GTFS_ZIP_URL = "https://gtfsrt.api.translink.com.au/GTFS/SEQ_GTFS.zip"
UPDATE_CHECK_INTERVAL = 3600

ROUTES_FILE = "routes.txt"
CALENDAR_FILE = "calendar.txt"
CALENDAR_DATES_FILE = "calendar_dates.txt"
TRIPS_FILE = "trips.txt"
STOPS_FILE = "stops.txt"
STOP_TIMES_FILE = "stop_times.txt"

FILES = [ROUTES_FILE, CALENDAR_FILE, CALENDAR_DATES_FILE, TRIPS_FILE, STOPS_FILE, STOP_TIMES_FILE]


class StaticGtfsHandler(MalamarService):
    """A service that handles static GTFS data."""

    def __init__(
        self,
        *,
        health_tracker: HealthTracker,
        data_store: GtfsDataStore,
        config: Configuration,
    ) -> None:
        """Initializes the GTFS static handler.

        Parameters
        ----------
        health_tracker : HealthTracker
            The health tracker to use for tracking the health of the service.
        data_store : GtfsDataStore
            The GTFS data store to use for data storage.
        config : Configuration
            The configuration to use for the service.
        """
        self._lock = asyncio.Lock()
        self._last_updated = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
        self._health_tracker = health_tracker
        self._data_store = data_store
        self._config = config
        super().__init__()

        self._update_static_gtfs_data.add_exception_type(aiohttp.ClientError)

    # region: GTFS data loading

    async def _download_gtfs_zip(self) -> ZipFile:
        """Downloads the GTFS zip file from the TransLink API."""
        async with aiohttp.ClientSession() as session:
            async with session.get(GTFS_ZIP_URL) as response:
                return ZipFile(BytesIO(await response.read()))

    def _load_static_data[T: Mapping[str, Any]](
        self,
        zip: ZipFile,
        filename: str,
        data_type: type[T],
        handler: Callable[[T], Any],
    ) -> None:
        with zip.open(filename) as f:
            reader = csv.DictReader(TextIOWrapper(f, encoding="utf-8"))
            for row in reader:
                handler(row)  # type: ignore

    def _load_static_gtfs_data(self, zip: ZipFile) -> None:
        """Loads the static GTFS data from the zip file."""
        self._data_store.clear()

        _log.debug("Adding routes...")
        self._load_static_data(zip, ROUTES_FILE, RouteData, self._data_store.add_route)

        _log.debug("Adding services...")
        self._load_static_data(zip, CALENDAR_DATES_FILE, CalendarDateData, self._data_store.add_service_exception)
        self._load_static_data(zip, CALENDAR_FILE, CalendarData, self._data_store.add_service)

        _log.debug("Adding trips...")
        self._load_static_data(zip, TRIPS_FILE, TripData, self._data_store.add_trip)

        _log.debug("Adding stops...")
        self._load_static_data(zip, STOPS_FILE, StopData, self._data_store.add_stop)

        _log.debug("Adding stop times...")
        self._load_static_data(zip, STOP_TIMES_FILE, StopTimeData, self._data_store.add_stop_time)

        _log.debug("Creating trip instances...")
        self._data_store.create_trip_instances()

    @loop(seconds=UPDATE_CHECK_INTERVAL)
    async def _update_static_gtfs_data(self) -> None:
        """Updates the static GTFS data from the TransLink API."""
        loop = asyncio.get_event_loop()

        async with self._lock:
            zip = await self._download_gtfs_zip()
            last_modified = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
            for file in FILES:
                last_modified = max(last_modified, datetime.datetime(*zip.getinfo(file).date_time, tzinfo=self._config.local_timezone))

            if last_modified > self._last_updated:
                _log.info("GTFS data out of date, updating...")
                await self._health_tracker.set_health(HealthStatusId.GTFS_AVAILABLE, False)
                await loop.run_in_executor(None, self._load_static_gtfs_data, zip)
                self._last_updated = last_modified
                await self._health_tracker.set_health(HealthStatusId.GTFS_AVAILABLE, True)
                _log.info("Successfully updated GTFS data")

            # Update trip instances.
            self._data_store.remove_old_trip_instances()
            self._data_store.create_trip_instances()

    # endregion

    async def start(self, *, timeout: float | None = None) -> None:
        """Starts the GTFS static handler.

        Paramters
        ----------
        timeout : float | None
            The maximum time to wait for the service to start.
        """
        self._update_static_gtfs_data.start()

    async def stop(self, *, timeout: float | None = None) -> None:
        """Stops the GTFS static handler.

        Paramters
        ----------
        timeout : float | None
            The maximum time to wait for the service to stop.
        """
        self._update_static_gtfs_data.stop()
