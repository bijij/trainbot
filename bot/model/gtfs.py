from __future__ import annotations

import asyncio
import csv
import datetime
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from difflib import get_close_matches
from enum import Enum, auto
from io import BytesIO, TextIOWrapper
from itertools import islice
from zipfile import ZipFile
from zoneinfo import ZoneInfo

import aiohttp
from audino import HealthTracker
from malamar import Service as MalamarService
from rayquaza import Mediator

from ..health import HealthStatusId
from ..mediator import (
    ChannelNames,
    GetNextServicesRequest,
    GetNextServicesResult,
    GetNextTrainsRequest,
    GetNextTrainsResult,
    SearchStopsRequest,
    SearchStopsResult,
)

GTFS_ZIP = "https://gtfsrt.api.translink.com.au/GTFS/SEQ_GTFS.zip"

ROUTES_FILE = "routes.txt"
SERVICES_FILE = "calendar.txt"
SERVICE_EXCEPTIONS_FILE = "calendar_dates.txt"
TRIPS_FILE = "trips.txt"
STOPS_FILE = "stops.txt"
STOP_TIMES_FILE = "stop_times.txt"

FILES = [ROUTES_FILE, SERVICES_FILE, SERVICE_EXCEPTIONS_FILE, TRIPS_FILE, STOPS_FILE, STOP_TIMES_FILE]

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

LAST_UPDATED: datetime.datetime = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)

ROUTES: dict[str, Route] = {}  # route_id -> Route

SERVICES: dict[str, Service] = {}  # service_id -> Service

TRIPS: dict[str, Trip] = {}  # trip_id -> Trip
TRIPS_BY_ROUTE: dict[str, list[Trip]] = defaultdict(list)  # route_id -> [Trip]

STOPS: dict[str, Stop] = {}  # stop_id -> Stop
STOPS_BY_NAME: dict[str, list[Stop]] = defaultdict(list)  # stop_name -> [Stop]

STOP_TIMES_BY_TRIP: dict[str, list[StopTime]] = defaultdict(list)  # trip_id -> [StopTime]
STOP_TIMES_BY_STOP: dict[str, list[StopTime]] = defaultdict(list)  # stop_id -> [StopTime]

TRIP_INSTANCES_BY_DATE: dict[datetime.date, dict[str, TripInstance]] = defaultdict(dict)  # date - > trip_id -> TripInstance
STOP_TIME_INSTANCES_BY_DATE: dict[datetime.date, dict[str, list[StopTimeInstance]]] = defaultdict(
    lambda: defaultdict(list)
)  # date -> trip_id -> StopTimeInstance
STOP_TIME_INSTANCES_BY_STOP: dict[str, list[StopTimeInstance]] = defaultdict(list)  # stop_id -> [StopTimeInstance]

# region: GTFS static data types

BRISBANE = ZoneInfo("Australia/Brisbane")


class Colour(Enum):
    RED = auto()
    BLUE = auto()
    GREEN = auto()
    GOLD = auto()
    PURPLE = auto()
    CYAN = auto()
    GREY = auto()
    WHITE = auto()


RAIL_COLOUR_MAP = {
    "GY": Colour.GREEN,
    "NA": Colour.GREEN,
    "CA": Colour.GREEN,
    "RP": Colour.CYAN,
    "SH": Colour.BLUE,
    "BD": Colour.GOLD,
    "DB": Colour.PURPLE,
    "FG": Colour.RED,
    "BR": Colour.GREY,
    "CL": Colour.BLUE,
    "BN": Colour.RED,
    "VL": Colour.GOLD,
    "SP": Colour.CYAN,
    "IP": Colour.GREEN,
    "RW": Colour.GREEN,
}

BUS_COLOUR_MAP = {
    "M1": Colour.BLUE,
    "M2": Colour.BLUE,
    "30": Colour.GOLD,
    "40": Colour.RED,
    "50": Colour.RED,
    "60": Colour.BLUE,
    "61": Colour.RED,
}


FERRY_COLOUR_MAP = {
    "F1": Colour.BLUE,
    "F11": Colour.GREEN,
    "F12": Colour.PURPLE,
    "F21": Colour.CYAN,
    "F22": Colour.GOLD,
    "F23": Colour.RED,
    "F24": Colour.GREEN,
}


class RouteType(Enum):
    TRAM = 0
    RAIL = 2
    BUS = 3
    FERRY = 4


class Route:
    def __init__(self, id: str, *, short_name: str, long_name: str, type: RouteType) -> None:
        self.id: str = id
        self.short_name: str = short_name
        self.long_name: str = long_name
        self.type: RouteType = type

    @property
    def trips(self) -> list[Trip]:
        return TRIPS_BY_ROUTE[self.id]

    @property
    def colour(self) -> Colour:
        match self.type:
            case RouteType.TRAM:
                return Colour.GOLD
            case RouteType.RAIL:
                return RAIL_COLOUR_MAP.get(self.short_name[2:], Colour.GREY)
            case RouteType.BUS:
                return BUS_COLOUR_MAP.get(self.short_name, Colour.PURPLE)
            case RouteType.FERRY:
                return FERRY_COLOUR_MAP.get(self.short_name, Colour.CYAN)


class Service:
    def __init__(
        self,
        id: str,
        *,
        days: Iterable[int],
        start_date: datetime.date,
        end_date: datetime.date,
        exceptions: Mapping[datetime.date, bool],
    ) -> None:
        self.id: str = id
        self.days: set[int] = set(days)
        self.start_date: datetime.date = start_date
        self.end_date: datetime.date = end_date
        self.exceptions: dict[datetime.date, bool] = dict(exceptions)

    def runs_on(self, date: datetime.date) -> bool:
        """Returns whether the service runs on the given date"""
        if date in self.exceptions:
            return self.exceptions[date]

        return self.start_date <= date <= self.end_date and date.weekday() in self.days


class Direction(Enum):
    UPWARD = 0
    DOWNWARD = 1


def load_time(time: str) -> datetime.timedelta:
    hours, minutes, seconds = map(int, time.split(":"))
    return datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds)


class Trip:

    def __init__(
        self,
        id: str,
        *,
        route_id: str,
        service_id: str,
        headsign: str,
        direction: Direction,
    ) -> None:
        self.id: str = id
        self._route_id: str = route_id
        self._service_id: str = service_id
        self.headsign: str = headsign
        self.direction: Direction = direction

    @property
    def route(self) -> Route:
        return ROUTES[self._route_id]

    @property
    def service(self) -> Service:
        return SERVICES[self._service_id]

    @property
    def stop_times(self) -> Sequence[StopTime]:
        return STOP_TIMES_BY_TRIP[self.id]


class LocationType(Enum):
    STOP = 0
    STATION = 1


class Stop:

    def __init__(
        self,
        id: str,
        *,
        name: str,
        url: str,
        type: LocationType,
        parent_stop_id: str | None,
        platform_code: str | None,
    ) -> None:
        self.id: str = id
        self.name: str = name
        self.url: str = url
        self.type: LocationType = type
        self._parent_stop_id: str | None = parent_stop_id
        self.platform_code: str | None = platform_code

    @property
    def parent(self) -> Stop | None:
        if self._parent_stop_id is None:
            return None

        return STOPS.get(self._parent_stop_id)

    @property
    def stop_times(self) -> Sequence[StopTime]:
        return STOP_TIMES_BY_STOP[self.id]

    @property
    def stop_time_instances(self) -> Sequence[StopTimeInstance]:
        return STOP_TIME_INSTANCES_BY_STOP[self.id]

    def get_stop_time_instances_between(self, start: datetime.datetime, end: datetime.datetime) -> Iterable[StopTimeInstance]:
        for stop_time_instance in self.stop_time_instances:
            if start <= stop_time_instance.scheduled_departure_time <= end:
                yield stop_time_instance


class StopTime:
    def __init__(
        self,
        *,
        trip_id: str,
        sequence: int,
        stop_id: str,
        arrival_time: datetime.timedelta,
        departure_time: datetime.timedelta,
        terminates: bool,
    ) -> None:
        self._trip_id: str = trip_id
        self.sequence: int = sequence
        self._stop_id: str = stop_id
        self.arrival_time: datetime.timedelta = arrival_time
        self.departure_time: datetime.timedelta = departure_time
        self.terminates: bool = terminates

    @property
    def trip(self) -> Trip:
        return TRIPS[self._trip_id]

    @property
    def stop(self) -> Stop:
        return STOPS[self._stop_id]


# endregion

# region: GTFS Realtime types


class StopTimeInstance(StopTime):
    def __init__(self, stop_time: StopTime, date: datetime.date) -> None:
        super().__init__(
            trip_id=stop_time._trip_id,
            sequence=stop_time.sequence,
            stop_id=stop_time._stop_id,
            arrival_time=stop_time.arrival_time,
            departure_time=stop_time.departure_time,
            terminates=stop_time.terminates,
        )
        self.date: datetime.date = date

    @property
    def scheduled_arrival_time(self) -> datetime.datetime:
        return datetime.datetime.combine(self.date, datetime.time(), tzinfo=BRISBANE) + self.arrival_time

    @property
    def scheduled_departure_time(self) -> datetime.datetime:
        return datetime.datetime.combine(self.date, datetime.time(), tzinfo=BRISBANE) + self.departure_time

    @property
    def trip(self) -> TripInstance:
        return TRIP_INSTANCES_BY_DATE[self.date][self._trip_id]


class TripInstance(Trip):
    def __init__(self, trip: Trip, date: datetime.date) -> None:
        super().__init__(
            id=trip.id,
            route_id=trip._route_id,
            service_id=trip._service_id,
            headsign=trip.headsign,
            direction=trip.direction,
        )
        self.date: datetime.date = date

    @property
    def stop_times(self) -> Sequence[StopTimeInstance]:
        return STOP_TIME_INSTANCES_BY_DATE[self.date][self.id]


# endregion


class Gtfs(MalamarService):

    def __init__(self, *, health_tracker: HealthTracker, mediator: Mediator) -> None:
        self.health_tracker = health_tracker
        self.mediator = mediator
        super().__init__()

    # region: GTFS data loading

    async def download_gtfs_zip(self) -> ZipFile:
        async with aiohttp.ClientSession() as session:
            async with session.get(GTFS_ZIP) as response:
                return ZipFile(BytesIO(await response.read()))

    def load_static_gtfs_data(self, zip: ZipFile) -> None:
        """Loads the static GTFS data from the zip file."""
        with zip.open(ROUTES_FILE) as f:
            reader = csv.DictReader(TextIOWrapper(f, "utf-8"))
            for row in reader:
                route_id = row["route_id"]
                ROUTES[route_id] = Route(
                    id=route_id,
                    short_name=row["route_short_name"],
                    long_name=row["route_long_name"],
                    type=RouteType(int(row["route_type"])),
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
                service_id = row["service_id"]

                SERVICES[service_id] = Service(
                    id=service_id,
                    days=[DAYS.index(day) for day in DAYS if row[day] == "1"],
                    start_date=datetime.datetime.strptime(row["start_date"], "%Y%m%d").date(),
                    end_date=datetime.datetime.strptime(row["end_date"], "%Y%m%d").date(),
                    exceptions=service_exceptions[service_id],
                )

        with zip.open(TRIPS_FILE) as f:
            reader = csv.DictReader(TextIOWrapper(f, "utf-8"))
            for row in reader:
                trip_id = row["trip_id"]
                route_id = row["route_id"]
                TRIPS[trip_id] = Trip(
                    id=trip_id,
                    route_id=route_id,
                    service_id=row["service_id"],
                    headsign=row["trip_headsign"],
                    direction=(Direction.UPWARD if row["direction_id"] == "0" else Direction.DOWNWARD),
                )
                TRIPS_BY_ROUTE[route_id].append(TRIPS[trip_id])

        with zip.open(STOPS_FILE) as f:
            reader = csv.DictReader(TextIOWrapper(f, "utf-8"))
            for row in reader:
                stop_id = row["stop_id"]
                stop_name = row["stop_name"]
                STOPS[stop_id] = Stop(
                    id=stop_id,
                    name=stop_name,
                    url=row["stop_url"],
                    type=LocationType(int(row["location_type"])),
                    parent_stop_id=row["parent_station"] or None,
                    platform_code=row["platform_code"] or None,
                )
                STOPS_BY_NAME[stop_name.lower()].append(STOPS[stop_id])

        with zip.open(STOP_TIMES_FILE) as f:
            reader = csv.DictReader(TextIOWrapper(f, "utf-8"))
            for row in reader:
                trip_id = row["trip_id"]
                stop_id = row["stop_id"]
                STOP_TIMES_BY_TRIP[trip_id].append(
                    StopTime(
                        trip_id=trip_id,
                        sequence=int(row["stop_sequence"]),
                        stop_id=stop_id,
                        arrival_time=load_time(row["arrival_time"]),
                        departure_time=load_time(row["departure_time"]),
                        terminates=row["pickup_type"] == "1",
                    )
                )
                STOP_TIMES_BY_STOP[stop_id].append(STOP_TIMES_BY_TRIP[trip_id][-1])
                if STOPS[stop_id].parent is not None:
                    STOP_TIMES_BY_STOP[STOPS[stop_id].parent.id].append(STOP_TIMES_BY_TRIP[trip_id][-1])  # type: ignore

        # Sort the stop times by sequence
        for stop_times in STOP_TIMES_BY_TRIP.values():
            stop_times.sort(key=lambda stop_time: stop_time.sequence)

        # Sort the stop times by departure time
        for stop_times in STOP_TIMES_BY_STOP.values():
            stop_times.sort(key=lambda stop_time: stop_time.departure_time)

        # Populate the trip instances and stop time instances for yesterday, today, and tomorrow
        date = datetime.date.today() - datetime.timedelta(days=1)
        for _ in range(3):
            for trip in TRIPS.values():
                if trip.service.runs_on(date):
                    TRIP_INSTANCES_BY_DATE[date][trip.id] = TripInstance(trip, date)
                    for stop_time in trip.stop_times:
                        STOP_TIME_INSTANCES_BY_DATE[date][trip.id].append(StopTimeInstance(stop_time, date))

            date += datetime.timedelta(days=1)

        # Populate the stop times instances for the next 3 days
        for date in STOP_TIME_INSTANCES_BY_DATE.keys():
            for stop_time_instances in STOP_TIME_INSTANCES_BY_DATE[date].values():
                for stop_time_instance in stop_time_instances:
                    STOP_TIME_INSTANCES_BY_STOP[stop_time_instance.stop.id].append(stop_time_instance)
                    if stop_time_instance.stop.parent is not None:
                        STOP_TIME_INSTANCES_BY_STOP[stop_time_instance.stop.parent.id].append(stop_time_instance)

        # Sort the stop time instances by scheduled departure time
        for stop_time_instances in STOP_TIME_INSTANCES_BY_STOP.values():
            stop_time_instances.sort(key=lambda stop_time_instance: stop_time_instance.scheduled_departure_time)

    async def update_static_gtfs_data(self) -> None:
        """Updates the static GTFS data from the TransLink API."""
        global LAST_UPDATED
        zip = await self.download_gtfs_zip()
        last_modified = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
        for file in FILES:
            last_modified = max(last_modified, datetime.datetime(*zip.getinfo(file).date_time, tzinfo=BRISBANE))

        if last_modified > LAST_UPDATED:
            print("GTFS data out of date, updating...")
            await self.health_tracker.set_health(HealthStatusId.GTFS_AVAILABLE, False)
            await asyncio.get_event_loop().run_in_executor(None, self.load_static_gtfs_data, zip)
            LAST_UPDATED = last_modified
            await self.health_tracker.set_health(HealthStatusId.GTFS_AVAILABLE, True)
            print("Successfully updated GTFS data")

    # endregion

    # region: Mediator message handlers

    async def handle_search_stops_request(self, request: SearchStopsRequest) -> SearchStopsResult:
        MAX_RESULTS = 25
        matches = []

        if request.query:
            for match in get_close_matches(request.query.lower(), STOPS_BY_NAME.keys(), n=MAX_RESULTS, cutoff=0.1):
                for stop in STOPS_BY_NAME[match]:
                    if ((not request.parent_only) or stop.parent is None) and any(
                        stop_time.trip.route.type is request.route_type for stop_time in stop.stop_times
                    ):
                        matches.append(stop)

        return SearchStopsResult(stops=matches[:MAX_RESULTS])

    async def handle_get_next_services_request(self, request: GetNextServicesRequest) -> GetNextServicesResult:
        stop = STOPS[request.stop_id]
        now = datetime.datetime.now(datetime.timezone.utc)
        lookahead_window = now + datetime.timedelta(hours=8)

        services = islice(
            (
                stop_time_instance
                for stop_time_instance in stop.get_stop_time_instances_between(now, lookahead_window)
                if stop_time_instance.trip.route.type is request.route_type and not stop_time_instance.terminates
            ),
            10,
        )

        return GetNextServicesResult(stop, services=list(services))

    async def handle_get_next_trains_request(self, request: GetNextTrainsRequest) -> GetNextTrainsResult:
        stop = STOPS[request.stop_id]
        now = datetime.datetime.now(datetime.timezone.utc)
        lookahead_window = now + datetime.timedelta(hours=4)

        down_trains = islice(
            (
                stop_time_instance
                for stop_time_instance in stop.get_stop_time_instances_between(now, lookahead_window)
                if stop_time_instance.trip.route.type is RouteType.RAIL
                and stop_time_instance.trip.direction == Direction.DOWNWARD
                and not stop_time_instance.terminates
            ),
            6,
        )
        up_trains = islice(
            (
                stop_time_instance
                for stop_time_instance in stop.get_stop_time_instances_between(now, lookahead_window)
                if stop_time_instance.trip.route.type is RouteType.RAIL
                and stop_time_instance.trip.direction == Direction.UPWARD
                and not stop_time_instance.terminates
            ),
            6,
        )

        return GetNextTrainsResult(stop, down_trains=list(down_trains), up_trains=list(up_trains))

    # endregion

    async def start(self, *, timeout: float | None = None) -> None:
        self.mediator.create_subscription(ChannelNames.GTFS, SearchStopsRequest, self.handle_search_stops_request)
        self.mediator.create_subscription(ChannelNames.GTFS, GetNextTrainsRequest, self.handle_get_next_trains_request)
        self.mediator.create_subscription(ChannelNames.GTFS, GetNextServicesRequest, self.handle_get_next_services_request)

        await self.update_static_gtfs_data()

    async def stop(self, *, timeout: float | None = None) -> None: ...
