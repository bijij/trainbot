from __future__ import annotations

import datetime
from collections.abc import Iterable, Mapping, Sequence
from enum import Enum, auto
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from ...utils import MISSING

if TYPE_CHECKING:
    from .store import GtfsDataStore

BRISBANE = ZoneInfo("Australia/Brisbane")

# region: GTFS static data types

__all__ = (
    "Colour",
    "Direction",
    "LocationType",
    "Route",
    "RouteType",
    "Service",
    "Stop",
    "StopTime",
    "Trip",
    "TripInstance",
    "StopTimeInstance",
)


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


class Direction(Enum):
    UPWARD = 0
    DOWNWARD = 1


class LocationType(Enum):
    STOP = 0
    STATION = 1


class GtfsData:

    def __init__(self, data_store: GtfsDataStore) -> None:
        self.data_store = data_store


class Route(GtfsData):
    def __init__(self, id: str, *, short_name: str, long_name: str, type: RouteType) -> None:
        self.id: str = id
        self.short_name: str = short_name
        self.long_name: str = long_name
        self.type: RouteType = type

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

    @property
    def trips(self) -> Sequence[Trip]:
        return self.data_store.get_trips_by_route(self.id)


class Service(GtfsData):
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

    @property
    def trips(self) -> Sequence[Trip]:
        return self.data_store.get_trips_by_service(self.id)


class Trip(GtfsData):
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
        return self.data_store.get_route(self._route_id)

    @property
    def service(self) -> Service:
        return self.data_store.get_service(self._service_id)

    @property
    def stop_times(self) -> Sequence[StopTime]:
        return self.data_store.get_stop_times(self.id)


class Stop(GtfsData):

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
        self.parent_stop_id: str | None = parent_stop_id
        self.platform_code: str | None = platform_code

    @property
    def parent_stop(self) -> Stop | None:
        if self.parent_stop_id is not None:
            return self.data_store.get_stop(self.parent_stop_id)
        return None


class StopTime(GtfsData):
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
        return self.data_store.get_trip(self._trip_id)

    @property
    def stop(self) -> Stop:
        return self.data_store.get_stop(self._stop_id)


# endregion

# region: GTFS Realtime types


class StopTimeInstance(StopTime):
    trip: TripInstance  # type: ignore

    def __init__(self, stop_time: StopTime, date: datetime.date) -> None:
        super().__init__(
            trip_id=stop_time.trip.id,
            sequence=stop_time.sequence,
            stop_id=stop_time.stop.id,
            arrival_time=stop_time.arrival_time,
            departure_time=stop_time.departure_time,
            terminates=stop_time.terminates,
        )
        self.date: datetime.date = date
        self.skipped: bool = False
        self._actual_arrival_time: datetime.datetime | None = None
        self._actual_departure_time: datetime.datetime | None = None

    @property
    def scheduled_arrival_time(self) -> datetime.datetime:
        return datetime.datetime.combine(self.date, datetime.time(), tzinfo=BRISBANE) + self.arrival_time

    @property
    def scheduled_departure_time(self) -> datetime.datetime:
        return datetime.datetime.combine(self.date, datetime.time(), tzinfo=BRISBANE) + self.departure_time

    @property
    def actual_arrival_time(self) -> datetime.datetime:
        return self._actual_arrival_time or self.scheduled_arrival_time

    @property
    def actual_departure_time(self) -> datetime.datetime:
        return self._actual_departure_time or self.scheduled_departure_time

    @property
    def trip_instance(self) -> TripInstance:
        return self.data_store.get_trip_instance(self.trip.id, self.date)


class TripInstance(Trip):
    stop_times: Sequence[StopTimeInstance]  # type: ignore

    def __init__(self, trip: Trip, date: datetime.date) -> None:
        super().__init__(
            id=trip.id,
            route_id=trip.route.id,
            service_id=trip.service.id,
            headsign=trip.headsign,
            direction=trip.direction,
        )
        self.date: datetime.date = date
        self.cancelled: bool = False

    @property
    def stop_times(self) -> Sequence[StopTimeInstance]:
        return self.data_store.get_stop_time_instances(self.id, self.date)


# endregion
