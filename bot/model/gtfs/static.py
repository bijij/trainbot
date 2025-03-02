import asyncio
import csv
import datetime
from collections import defaultdict
from io import BytesIO, TextIOWrapper
from zipfile import ZipFile

import aiohttp
from audino import HealthTracker
from malamar import Service as MalamarService

from ...health import HealthStatusId
from .store import GtfsDataStore
from .types import BRISBANE, Direction, LocationType, Route, RouteType, Service, Stop, StopTime, Trip

__all__ = ("StaticGtfsHandler",)


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

    def __init__(self, *, health_tracker: HealthTracker, data_store: GtfsDataStore) -> None:
        self._lock = asyncio.Lock()
        self._last_updated = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
        self._health_tracker = health_tracker
        self._data_store = data_store
        super().__init__()

    # region: GTFS data loading

    async def download_gtfs_zip(self) -> ZipFile:
        """Downloads the GTFS zip file from the TransLink API."""
        async with aiohttp.ClientSession() as session:
            async with session.get(GTFS_ZIP_URL) as response:
                return ZipFile(BytesIO(await response.read()))

    async def load_static_gtfs_data(self, zip: ZipFile) -> None:
        """Loads the static GTFS data from the zip file."""
        await self._data_store.clear()

        with zip.open(ROUTES_FILE) as f:
            reader = csv.DictReader(TextIOWrapper(f, "utf-8"))
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
            reader = csv.DictReader(TextIOWrapper(f, "utf-8"))
            for row in reader:
                service_exceptions[row["service_id"]][datetime.datetime.strptime(row["date"], "%Y%m%d").date()] = (
                    row["exception_type"] == "1"
                )

        with zip.open(SERVICES_FILE) as f:
            reader = csv.DictReader(TextIOWrapper(f, "utf-8"))
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

        with zip.open(TRIPS_FILE) as f:
            reader = csv.DictReader(TextIOWrapper(f, "utf-8"))
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

        with zip.open(STOPS_FILE) as f:
            reader = csv.DictReader(TextIOWrapper(f, "utf-8"))
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

        with zip.open(STOP_TIMES_FILE) as f:
            reader = csv.DictReader(TextIOWrapper(f, "utf-8"))
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

        await self._data_store.create_trip_instances()

    async def update_static_gtfs_data(self) -> None:
        """Updates the static GTFS data from the TransLink API."""
        zip = await self.download_gtfs_zip()
        last_modified = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
        for file in FILES:
            last_modified = max(last_modified, datetime.datetime(*zip.getinfo(file).date_time, tzinfo=BRISBANE))

        if last_modified > self._last_updated:
            print("GTFS data out of date, updating...")
            await self._health_tracker.set_health(HealthStatusId.GTFS_AVAILABLE, False)
            await self.load_static_gtfs_data(zip)
            self._last_updated = last_modified
            await self._health_tracker.set_health(HealthStatusId.GTFS_AVAILABLE, True)
            print("Successfully updated GTFS data")

        # Update trip instances.
        await self._data_store.remove_old_trip_instances()
        await self._data_store.create_trip_instances()

    # endregion

    async def start(self, *, timeout: float | None = None) -> None:
        while True:
            async with self._lock:
                await self.update_static_gtfs_data()
            await asyncio.sleep(UPDATE_CHECK_INTERVAL)

    async def stop(self, *, timeout: float | None = None) -> None: ...
