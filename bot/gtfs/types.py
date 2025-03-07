from __future__ import annotations

import datetime
from collections.abc import Iterable, Mapping, Sequence
from enum import Enum, auto
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from .store import GtfsDataStore

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
    """Represents a colour."""

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
    """Represents a route type."""

    TRAM = 0
    RAIL = 2
    BUS = 3
    FERRY = 4


class Direction(Enum):
    """Represents a direction."""

    UPWARD = 0
    DOWNWARD = 1


class LocationType(Enum):
    """Represents a location type."""

    STOP = 0
    STATION = 1


class _GtfsData:
    _data_store: GtfsDataStore | None = None

    def register(self, data_store: GtfsDataStore) -> Self:
        """Registers this object with the given GTFS data store.

        Parameters
        ----------
        data_store : GtfsDataStore
            The GTFS data store.

        Returns
        -------
        Self
            This object so that methods can be chained.
        """
        if self._data_store is not None:
            raise RuntimeError("This object is already registered with a GTFS data store.")
        self._data_store = data_store

        return self


class Route(_GtfsData):
    """Represents a route.

    Attributes
    ----------
    id : str
        The route ID.
    short_name : str
        The short name of the route.
    long_name : str
        The long name of the route.
    type : RouteType
        The type of the route.
    """

    def __init__(
        self,
        /,
        id: str,
        *,
        short_name: str,
        long_name: str,
        type: RouteType,
    ) -> None:
        """Initializes the route.

        Parameters
        ----------
        data_store : GtfsDataStore
            The GTFS data store.
        id : str
            The route ID.
        short_name : str
            The short name of the route.
        long_name : str
            The long name of the route.
        type : RouteType
            The type of the route.
        """
        self.id: str = id
        self.short_name: str = short_name
        self.long_name: str = long_name
        self.type: RouteType = type

    @property
    def colour(self) -> Colour:
        """Colour: The colour of the route."""
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
        """Sequence[Trip]: The trips on this route."""
        if self._data_store is None:
            raise RuntimeError("This route is not registered with a GTFS data store.")

        return self._data_store.get_trips_by_route(self.id)


class Service(_GtfsData):
    """Represents a service.

    Attributes
    ----------
    id : str
        The service ID.
    days : set[int]
        The days the service runs.
    start_date : datetime.date
        The start date of the service.
    end_date : datetime.date
        The end date of the service.
    exceptions : dict[datetime.date, bool]
        The exceptions to the service.
    """

    def __init__(
        self,
        /,
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
        """Returns whether the service runs on the given date

        Parameters
        ----------
        date : datetime.date
            The date to check.

        Returns
        -------
        bool
            Whether the service runs on the given date.
        """
        if date in self.exceptions:
            return self.exceptions[date]

        return self.start_date <= date <= self.end_date and date.weekday() in self.days

    @property
    def trips(self) -> Sequence[Trip]:
        """Sequence[Trip]: The trips on this service."""
        if self._data_store is None:
            raise RuntimeError("This service is not registered with a GTFS data store.")

        return self._data_store.get_trips_by_service(self.id)


class Trip(_GtfsData):
    """Represents a trip.

    Attributes
    ----------
    id : str
        The trip ID.
    route_id : str
        The route ID.
    service_id : str
        The service ID.
    headsign : str
        The headsign of the trip.
    direction : Direction
        The direction of the trip.
    """

    def __init__(
        self,
        /,
        id: str,
        *,
        route_id: str,
        service_id: str,
        headsign: str,
        direction: Direction,
    ) -> None:
        """Initializes the trip.

        Parameters
        ----------
        id : str
            The trip ID.
        route_id : str
            The route ID.
        service_id : str
            The service ID.
        headsign : str
            The headsign of the trip.
        direction : Direction
            The direction of the trip.
        """
        self.id: str = id
        self._route_id: str = route_id
        self._service_id: str = service_id
        self.headsign: str = headsign
        self.direction: Direction = direction

    @property
    def route(self) -> Route:
        """Route: The route of the trip."""
        if self._data_store is None:
            raise RuntimeError("This trip is not registered with a GTFS data store.")

        return self._data_store.get_route(self._route_id)

    @property
    def service(self) -> Service:
        """Service: The service of the trip."""
        if self._data_store is None:
            raise RuntimeError("This trip is not registered with a GTFS data store.")

        return self._data_store.get_service(self._service_id)

    @property
    def stop_times(self) -> Sequence[StopTime]:
        """Sequence[StopTime]: The stop times of the trip."""
        if self._data_store is None:
            raise RuntimeError("This trip is not registered with a GTFS data store.")

        return self._data_store.get_stop_times(self.id)


class Stop(_GtfsData):
    """Represents a stop.

    Attributes
    ----------
    id : str
        The stop ID.
    name : str
        The name of the stop.
    url : str
        The URL of the stop.
    type : LocationType
        The type of the stop.
    parent_stop_id : str | None
        The parent stop ID.
    platform_code : str | None
        The platform code.
    """

    def __init__(
        self,
        /,
        id: str,
        *,
        name: str,
        url: str,
        type: LocationType,
        parent_stop_id: str | None,
        platform_code: str | None,
    ) -> None:
        """Initializes the stop.

        Parameters
        ----------
        id : str
            The stop ID.
        name : str
            The name of the stop.
        url : str
            The URL of the stop.
        type : LocationType
            The type of the stop.
        parent_stop_id : str | None
            The parent stop ID.
        platform_code : str | None
            The platform code.
        """
        self.id: str = id
        self.name: str = name
        self.url: str = url
        self.type: LocationType = type
        self.parent_stop_id: str | None = parent_stop_id
        self.platform_code: str | None = platform_code

    @property
    def parent_stop(self) -> Stop | None:
        """Stop | None: The parent stop of the stop."""
        if self._data_store is None:
            raise RuntimeError("This stop is not registered with a GTFS data store.")

        if self.parent_stop_id is not None:
            return self._data_store.get_stop(self.parent_stop_id)
        return None


class StopTime(_GtfsData):
    def __init__(
        self,
        /,
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
        """Trip: The trip of the stop time."""
        if self._data_store is None:
            raise RuntimeError("This stop time is not registered with a GTFS data store.")

        return self._data_store.get_trip(self._trip_id)

    @property
    def stop(self) -> Stop:
        """Stop: The stop of the stop time."""
        if self._data_store is None:
            raise RuntimeError("This stop time is not registered with a GTFS data store.")

        return self._data_store.get_stop(self._stop_id)


# endregion

# region: GTFS Realtime types


class TripInstance(Trip):
    """Represents a trip instance.

    Attributes
    ----------
    id : str
        The trip ID.
    route_id : str
        The route ID.
    service_id : str
        The service ID.
    headsign : str
        The headsign of the trip.
    direction : Direction
        The direction of the trip.
    date : datetime.date
        The date of the trip instance.
    cancelled : bool
        Whether the trip instance has been or will be cancelled.
    """

    def __init__(self, trip: Trip, date: datetime.date) -> None:
        """Initializes the trip instance.

        Parameters
        ----------
        trip : Trip
            The trip.
        date : datetime.date
            The date of the trip instance.
        """
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
        """Sequence[StopTimeInstance]: The stop time instances of the trip instance."""
        if self._data_store is None:
            raise RuntimeError("This trip instance is not registered with a GTFS data store.")

        return self._data_store.get_stop_time_instances(self.id, self.date)


class StopTimeInstance(StopTime):
    """Represents a stop time instance.

    Attributes
    ----------
    trip_id : str
        The trip ID.
    sequence : int
        The sequence of the stop time.
    stop_id : str
        The stop ID.
    arrival_time : datetime.timedelta
        The arrival time.
    departure_time : datetime.timedelta
        The departure time.
    terminates : bool
        Whether the trip terminates at this stop.
    date : datetime.date
        The date of the stop time instance.
    skipped : bool
        Whether the stop time instance has been or will be skipped.
    """

    def __init__(self, stop_time: StopTime, date: datetime.date) -> None:
        """Initializes the stop time instance.

        Parameters
        ----------
        stop_time : StopTime
            The stop time.
        date : datetime.date
            The date of the stop time instance.
        """
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
        """datetime.datetime: The scheduled arrival time of the stop time instance."""
        if self._data_store is None:
            raise RuntimeError("This stop time instance is not registered with a GTFS data store.")

        return datetime.datetime.combine(self.date, datetime.time(), tzinfo=self._data_store._config.local_timezone) + self.arrival_time

    @property
    def scheduled_departure_time(self) -> datetime.datetime:
        """datetime.datetime: The scheduled departure time of the stop time instance."""
        if self._data_store is None:
            raise RuntimeError("This stop time instance is not registered with a GTFS data store.")

        return datetime.datetime.combine(self.date, datetime.time(), tzinfo=self._data_store._config.local_timezone) + self.departure_time

    @property
    def actual_arrival_time(self) -> datetime.datetime:
        """datetime.datetime: The actual arrival time of the stop time instance."""
        return self._actual_arrival_time or self.scheduled_arrival_time

    @property
    def actual_departure_time(self) -> datetime.datetime:
        """datetime.datetime: The actual departure time of the stop time instance."""
        return self._actual_departure_time or self.scheduled_departure_time

    @property
    def trip(self) -> TripInstance:
        """TripInstance: The trip instance this stop time instance belongs to."""
        if self._data_store is None:
            raise RuntimeError("This stop time instance is not registered with a GTFS data store.")

        return self._data_store.get_trip_instance(self._trip_id, self.date)


# endregion
