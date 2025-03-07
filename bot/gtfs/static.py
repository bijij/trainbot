import asyncio
import csv
import datetime
import logging
from collections import defaultdict
from io import BytesIO, TextIOWrapper
from zipfile import ZipFile

import aiohttp
from audino import HealthTracker
from discord.ext.tasks import loop
from malamar import Service as MalamarService

from ..configuration import Configuration
from ..health import HealthStatusId
from .store import GtfsDataStore
from .types import Direction, LocationType, Route, RouteType, Service, Stop, StopTime, Trip

__all__ = ("StaticGtfsHandler",)


_log = logging.getLogger(__name__)


GTFS_ZIP_URL = "https://gtfsrt.api.translink.com.au/GTFS/SEQ_GTFS.zip"
UPDATE_CHECK_INTERVAL = 3600

ROUTES_FILE = "routes.txt"
SERVICES_FILE = "calendar.txt"
SERVICE_EXCEPTIONS_FILE = "calendar_dates.txt"
TRIPS_FILE = "trips.txt"
STOPS_FILE = "stops.txt"
STOP_TIMES_FILE = "stop_times.txt"

FILES = [ROUTES_FILE, SERVICES_FILE, SERVICE_EXCEPTIONS_FILE, TRIPS_FILE, STOPS_FILE, STOP_TIMES_FILE]

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def load_time(time: str) -> datetime.timedelta:
    hours, minutes, seconds = map(int, time.split(":"))
    return datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds)


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

    async def _load_static_gtfs_data(self, zip: ZipFile) -> None:
        """Loads the static GTFS data from the zip file."""
        await self._data_store.clear()

        loop = asyncio.get_running_loop()

        _log.debug("Adding routes...")
        with zip.open(ROUTES_FILE) as f:
            reader = await loop.run_in_executor(None, csv.DictReader, TextIOWrapper(f, "utf-8"))
            for row in reader:
                await self._data_store.add_route(
                    Route(
                        id=row["route_id"],
                        short_name=row["route_short_name"],
                        long_name=row["route_long_name"],
                        type=RouteType(int(row["route_type"])),
                    )
                )

        service_exceptions: dict[str, dict[datetime.date, bool]] = defaultdict(dict)

        with zip.open(SERVICE_EXCEPTIONS_FILE) as f:
            reader = await loop.run_in_executor(None, csv.DictReader, TextIOWrapper(f, "utf-8"))
            for row in reader:
                service_exceptions[row["service_id"]][datetime.datetime.strptime(row["date"], "%Y%m%d").date()] = (
                    row["exception_type"] == "1"
                )

        _log.debug("Adding services...")
        with zip.open(SERVICES_FILE) as f:
            reader = await loop.run_in_executor(None, csv.DictReader, TextIOWrapper(f, "utf-8"))
            for row in reader:
                await self._data_store.add_service(
                    Service(
                        id=row["service_id"],
                        days=[DAYS.index(day) for day in DAYS if row[day] == "1"],
                        start_date=datetime.datetime.strptime(row["start_date"], "%Y%m%d").date(),
                        end_date=datetime.datetime.strptime(row["end_date"], "%Y%m%d").date(),
                        exceptions=service_exceptions[row["service_id"]],
                    )
                )

        _log.debug("Adding trips...")
        with zip.open(TRIPS_FILE) as f:
            reader = await loop.run_in_executor(None, csv.DictReader, TextIOWrapper(f, "utf-8"))
            for row in reader:
                await self._data_store.add_trip(
                    Trip(
                        id=row["trip_id"],
                        route_id=row["route_id"],
                        service_id=row["service_id"],
                        headsign=row["trip_headsign"],
                        direction=(Direction.UPWARD if row["direction_id"] == "0" else Direction.DOWNWARD),
                    )
                )

        _log.debug("Adding stops...")
        with zip.open(STOPS_FILE) as f:
            reader = await loop.run_in_executor(None, csv.DictReader, TextIOWrapper(f, "utf-8"))
            for row in reader:
                await self._data_store.add_stop(
                    Stop(
                        id=row["stop_id"],
                        name=row["stop_name"],
                        url=row["stop_url"],
                        type=LocationType(int(row["location_type"])),
                        parent_stop_id=row["parent_station"] or None,
                        platform_code=row["platform_code"] or None,
                    )
                )

        _log.debug("Adding stop times...")
        with zip.open(STOP_TIMES_FILE) as f:
            reader = await loop.run_in_executor(None, csv.DictReader, TextIOWrapper(f, "utf-8"))
            for row in reader:
                await self._data_store.add_stop_time(
                    StopTime(
                        trip_id=row["trip_id"],
                        sequence=int(row["stop_sequence"]),
                        stop_id=row["stop_id"],
                        arrival_time=load_time(row["arrival_time"]),
                        departure_time=load_time(row["departure_time"]),
                        terminates=row["pickup_type"] == "1",
                    )
                )

        _log.debug("Creating trip instances...")
        await self._data_store.create_trip_instances()

    @loop(seconds=UPDATE_CHECK_INTERVAL)
    async def _update_static_gtfs_data(self) -> None:
        """Updates the static GTFS data from the TransLink API."""
        async with self._lock:
            zip = await self._download_gtfs_zip()
            last_modified = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
            for file in FILES:
                last_modified = max(last_modified, datetime.datetime(*zip.getinfo(file).date_time, tzinfo=self._config.local_timezone))

            if last_modified > self._last_updated:
                _log.info("GTFS data out of date, updating...")
                await self._health_tracker.set_health(HealthStatusId.GTFS_AVAILABLE, False)
                await self._load_static_gtfs_data(zip)
                self._last_updated = last_modified
                await self._health_tracker.set_health(HealthStatusId.GTFS_AVAILABLE, True)
                _log.info("Successfully updated GTFS data")

            # Update trip instances.
            await self._data_store.remove_old_trip_instances()
            await self._data_store.create_trip_instances()

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
