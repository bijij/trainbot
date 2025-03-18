import datetime
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Literal, overload

from ..configuration import Configuration
from .types import *

__all__ = ("GtfsDataStore",)


_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _load_time(time: str) -> datetime.timedelta:
    """Loads a time from a string in the format HH:MM:SS.

    Parameters
    ----------
    time : str
        The time to load.

    Returns
    -------
    datetime.timedelta
        The loaded time as a timedelta.
    """

    hours, minutes, seconds = map(int, time.split(":"))
    return datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds)


class GtfsDataStore:
    """Responsible for storing and managing GTFS data."""

    def __init__(
        self,
        config: Configuration,
    ) -> None:
        """Initializes the data store.

        Parameters
        ----------
        config : Configuration
            Configuration data required for the data store.
        """
        self._config = config

        # Static data
        self._routes: dict[str, Route] = {}
        self._services_exceptions: dict[str, dict[datetime.date, bool]] = defaultdict(dict)
        self._services: dict[str, Service] = {}
        self._trips: dict[str, Trip] = {}
        self._trips_by_route: dict[str, list[Trip]] = defaultdict(list)
        self._trips_by_service: dict[str, list[Trip]] = defaultdict(list)
        self._stops: dict[str, Stop] = {}
        self._children_stops: dict[str, list[Stop]] = defaultdict(list)
        self._stop_times_by_trip: dict[str, list[StopTime]] = defaultdict(list)
        self._route_types_by_stop: dict[str, set[RouteType]] = defaultdict(set)

        # Real-time data
        self._trip_instances_by_date: dict[datetime.date, dict[str, TripInstance]] = defaultdict(dict)
        self._stop_time_instances_by_date: dict[datetime.date, dict[str, dict[int, StopTimeInstance]]] = defaultdict(
            lambda: defaultdict(dict)
        )
        self._stop_time_instances_by_stop: dict[str, list[StopTimeInstance]] = defaultdict(list)

    def clear(self) -> None:
        """Clears all data from the data store."""
        self._routes.clear()
        self._services.clear()
        self._trips.clear()
        self._trips_by_route.clear()
        self._trips_by_service.clear()
        self._stops.clear()
        self._stop_times_by_trip.clear()
        self._trip_instances_by_date.clear()
        self._stop_time_instances_by_date.clear()
        self._stop_time_instances_by_stop.clear()

    def add_route(self, data: RouteData) -> None:
        """Adds a route to the data store and updates the route instances.

        Parameters
        ----------
        data : RouteData
            The route data to add to the data store.
        """
        route = Route(
            id=data["route_id"].lower(),
            short_name=data["route_short_name"],
            long_name=data["route_long_name"],
            type=RouteType(int(data["route_type"])),
            colour=data["route_color"],
        )

        self._routes[route.id] = route.register(self)

    def add_service_exception(self, data: CalendarDateData) -> None:
        """Adds a service exception to the data store.

        Parameters
        ----------
        data : CalendarDateData
            The service exception data to add to the data store
        """
        date = datetime.datetime.strptime(data["date"], "%Y%m%d").date()
        self._services_exceptions[data["service_id"]][date] = data["exception_type"] == 1

    def add_service(self, data: CalendarData) -> None:
        """Adds a service to the data store and updates the service instances.

        Parameters
        ----------
        data : CalendarData
            The service data to add to the data store.
        """
        service = Service(
            id=data["service_id"].lower(),
            days=[_DAYS.index(day) for day in _DAYS if data[day] == "1"],
            start_date=datetime.datetime.strptime(data["start_date"], "%Y%m%d").date(),
            end_date=datetime.datetime.strptime(data["end_date"], "%Y%m%d").date(),
        )

        self._services[service.id] = service.register(self)

    def add_trip(self, data: TripData) -> None:
        """Adds a trip to the data store and updates the trip instances.

        Parameters
        ----------
        data : TripData
            The trip data to add to the data store.
        """
        trip = Trip(
            id=data["trip_id"].lower(),
            route_id=data["route_id"].lower(),
            service_id=data["service_id"].lower(),
            headsign=data["trip_headsign"],
            direction=Direction.UPWARD if data["direction_id"] == "1" else Direction.DOWNWARD,
        )

        self._trips[trip.id] = trip.register(self)
        self._trips_by_route[trip._route_id].append(trip)
        self._trips_by_service[trip._service_id].append(trip)

    def add_stop(self, data: StopData) -> None:
        """Adds a stop to the data store and updates the stop instances.

        Parameters
        ----------
        data : StopData
            The stop data to add to the data store.
        """
        stop = Stop(
            id=data["stop_id"].lower(),
            name=data["stop_name"],
            url=data["stop_url"],
            type=LocationType(int(data["location_type"])),
            parent_station_id=data["parent_station"].lower() or None,
            platform_code=data["platform_code"] or None,
        )

        self._stops[stop.id] = stop.register(self)
        if stop._parent_station_id is not None:
            self._children_stops[stop._parent_station_id].append(stop)

    def add_stop_time(self, data: StopTimeData) -> None:
        """Adds a stop time to the data store and updates the stop time instances.

        Parameters
        ----------
        data : StopTimeData
            The stop time data to add to the data store.
        """
        stop_time = StopTime(
            trip_id=data["trip_id"].lower(),
            sequence=int(data["stop_sequence"]),
            stop_id=data["stop_id"].lower(),
            arrival_time=_load_time(data["arrival_time"]),
            departure_time=_load_time(data["departure_time"]),
            terminates=data["pickup_type"] == "1",
        ).register(self)

        self._stop_times_by_trip[stop_time._trip_id].append(stop_time)
        route_type = self._routes[stop_time.trip._route_id].type
        self._route_types_by_stop[stop_time._stop_id].add(route_type)

    def remove_old_trip_instances(self) -> None:
        """Removes trip instances for dates older than yesterday."""
        yesterday = datetime.date.today() - datetime.timedelta(days=1)

        for date in list(self._trip_instances_by_date.keys()):
            if date < yesterday:
                del self._trip_instances_by_date[date]

        for date in list(self._stop_time_instances_by_date.keys()):
            if date < yesterday:
                del self._stop_time_instances_by_date[date]

        for stop_id, stop_time_instances in self._stop_time_instances_by_stop.items():
            self._stop_time_instances_by_stop[stop_id] = [
                stop_time_instance for stop_time_instance in stop_time_instances if stop_time_instance.date >= yesterday
            ]

    def create_trip_instances(self) -> None:
        """Creates the trip instances for yesterday, today, and tomorrow."""
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)
        tomorrow = today + datetime.timedelta(days=1)

        dates = [yesterday, today, tomorrow]
        for date in dates:
            if not self._trip_instances_by_date[date]:
                for trip_id, trip in self._trips.items():
                    service = self._services[trip._service_id]
                    if service.runs_on(date):
                        self._trip_instances_by_date[date][trip_id] = TripInstance(trip, date).register(self)
                        for stop_time in self._stop_times_by_trip[trip_id]:
                            self._stop_time_instances_by_date[date][trip_id][stop_time.sequence] = StopTimeInstance(
                                stop_time, date
                            ).register(self)

                for stop_time_instances in self._stop_time_instances_by_date[date].values():
                    for stop_time_instance in stop_time_instances.values():
                        self._stop_time_instances_by_stop[stop_time_instance._stop_id].append(stop_time_instance)

    def set_trip_instance_status(self, trip_id: str, date: datetime.date, cancelled: bool) -> None:
        """Sets the status of a trip instance.

        Parameters
        ----------
        trip_id : str
            The ID of the trip.
        date : datetime.date
            The date of the trip instance.
        cancelled : bool
            Whether the trip instance is cancelled.
        """
        self._trip_instances_by_date[date][trip_id.lower()].cancelled = cancelled

    def set_stop_time_instance_status(self, trip_id: str, date: datetime.date, stop_sequence: int, skipped: bool) -> None:
        """Sets the status of a stop time instance.

        Parameters
        ----------
        trip_id : str
            The ID of the trip.
        date : datetime.date
            The date of the trip instance.
        stop_sequence : int
            The sequence of the stop time.
        skipped : bool
            Whether the stop has or will be skipped.
        """
        self._stop_time_instances_by_date[date][trip_id.lower()][stop_sequence].skipped = skipped

    def set_stop_time_actual_arrival_time(
        self, trip_id: str, date: datetime.date, stop_sequence: int, arrival_time: datetime.datetime
    ) -> None:
        """Sets the actual arrival time of a stop time instance.

        Parameters
        ----------
        trip_id : str
            The ID of the trip.
        date : datetime.date
            The date of the trip instance.
        stop_sequence : int
            The sequence of the stop time.
        arrival_time : datetime.datetime
            The actual arrival time of the stop time instance.
        """
        self._stop_time_instances_by_date[date][trip_id.lower()][stop_sequence]._actual_arrival_time = arrival_time

    def set_stop_time_actual_departure_time(
        self, trip_id: str, date: datetime.date, stop_sequence: int, departure_time: datetime.datetime
    ) -> None:
        """Sets the actual departure time of a stop time instance.

        Parameters
        ----------
        trip_id : str
            The ID of the trip.
        date : datetime.date
            The date of the trip instance.
        stop_sequence : int
            The sequence of the stop time.
        departure_time : datetime.datetime
            The actual departure time of the stop time instance.
        """
        self._stop_time_instances_by_date[date][trip_id.lower()][stop_sequence]._actual_departure_time = departure_time

    @overload
    def get_route(self, route_id: str, *, error_on_missing: Literal[True] = ...) -> Route: ...

    @overload
    def get_route(self, route_id: str, *, error_on_missing: Literal[False] | bool) -> Route | None: ...

    def get_route(self, route_id: str, *, error_on_missing: bool = True) -> Route | None:
        """Gets a route by its ID

        Parameters
        ----------
        route_id : str
            The ID of the route to get.
        error_on_missing : bool, optional
            Whether to raise an error if the route is missing, defaults to True.

        Returns
        -------
        Route
            The route with the specified ID, or None if not found.
        """
        result = self._routes.get(route_id.lower())
        if result is None and error_on_missing:
            raise ValueError(f"Route with ID '{route_id}' not found.")
        return result

    @overload
    def get_service(self, service_id: str, *, error_on_missing: Literal[True] = ...) -> Service: ...

    @overload
    def get_service(self, service_id: str, *, error_on_missing: Literal[False] | bool) -> Service | None: ...

    def get_service(self, service_id: str, *, error_on_missing: bool = True) -> Service | None:
        """Gets a service by its ID

        Parameters
        ----------
        service_id : str
            The ID of the service to get.
        error_on_missing : bool, optional
            Whether to raise an error if the service is missing, defaults to True.

        Returns
        -------
        Service
            The service with the specified ID.
        """
        result = self._services.get(service_id.lower())
        if result is None and error_on_missing:
            raise ValueError(f"Service with ID '{service_id}' not found.")
        return result

    def get_service_exceptions(self, service_id: str) -> Mapping[datetime.date, bool]:
        """Gets all service exceptions for a service

        Parameters
        ----------
        service_id : str
            The ID of the service to get the exceptions for.

        Returns
        -------
        Mapping[datetime.date, bool]
            The service exceptions for the specified service.
        """

        return self._services_exceptions[service_id.lower()]

    @overload
    def get_trip(self, trip_id: str, *, error_on_missing: Literal[True] = ...) -> Trip: ...

    @overload
    def get_trip(self, trip_id: str, *, error_on_missing: Literal[False] | bool) -> Trip | None: ...

    def get_trip(self, trip_id: str, *, error_on_missing: bool = True) -> Trip | None:
        """Gets a trip by its ID

        Parameters
        ----------
        trip_id : str
            The ID of the trip to get.
        error_on_missing : bool, optional
            Whether to raise an error if the trip is missing, defaults to True.

        Returns
        -------
        Trip
            The trip with the specified ID.
        """
        result = self._trips.get(trip_id.lower())
        if result is None and error_on_missing:
            raise ValueError(f"Trip with ID '{trip_id}' not found.")
        return result

    @overload
    def get_stop(self, stop_id: str, *, error_on_missing: Literal[True] = ...) -> Stop: ...

    @overload
    def get_stop(self, stop_id: str, *, error_on_missing: Literal[False] | bool) -> Stop | None: ...

    def get_stop(self, stop_id: str, *, error_on_missing: bool = True) -> Stop | None:
        """Gets a stop by its ID

        Parameters
        ----------
        stop_id : str
            The ID of the stop to get.
        error_on_missing : bool, optional
            Whether to raise an error if the stop is missing, defaults to True.

        Returns
        -------
        Stop
            The stop with the specified ID.
        """
        result = self._stops.get(stop_id.lower())
        if result is None and error_on_missing:
            raise ValueError(f"Stop with ID '{stop_id}' not found.")
        return result

    def _walk_child_stop_ids(self, parent_stop_id: str) -> Iterable[str]:
        """Walks all child stop IDs of a parent stop

        Parameters
        ----------
        parent_stop_id : str
            The ID of the parent stop to walk the children of.

        Returns
        -------
        Iterable[str]
            The IDs of all children stops of the parent stop, including the parent stop.
        """
        yield parent_stop_id
        for stop in self._children_stops[parent_stop_id]:
            yield from self._walk_child_stop_ids(stop.id)

    def stop_has_route_with_type(self, stop_id: str, route_type: RouteType) -> bool:
        """Checks if a stop has a route of a specific type

        Parameters
        ----------
        stop_id : str
            The ID of the stop to check.
        route_type : RouteType
            The route type to check for.

        Returns
        -------
        bool
            Whether the stop has a route of the specified type.
        """
        return route_type in self._route_types_by_stop[stop_id.lower()]

    def get_stops_by_route_type(self, route_type: RouteType) -> list[Stop]:
        """Gets all stops for a route type

        Parameters
        ----------
        route_type : RouteType
            The route type to get the stops for.

        Returns
        -------
        list[Stop]
            The stops for the specified route type.
        """
        return [
            stop
            for stop in self._stops.values()
            for stop_id in self._walk_child_stop_ids(stop.id)
            if self.stop_has_route_with_type(stop_id, route_type)
        ]

    def get_trips_by_route(self, route_id: str) -> Sequence[Trip]:
        """Gets all trips for a route

        Parameters
        ----------
        route_id : str
            The ID of the route to get the trips for.

        Returns
        -------
        Sequence[Trip]
            The trips for the specified route.
        """
        return self._trips_by_route[route_id.lower()]

    def get_trips_by_service(self, service_id: str) -> Sequence[Trip]:
        """Gets all trips for a service

        Parameters
        ----------
        service_id : str
            The ID of the service to get the trips for.

        Returns
        -------
        Sequence[Trip]
            The trips for the specified service.
        """
        return self._trips_by_service[service_id.lower()]

    @overload
    def get_trip_instance(self, trip_id: str, date: datetime.date, *, error_on_missing: Literal[True] = ...) -> TripInstance: ...

    @overload
    def get_trip_instance(self, trip_id: str, date: datetime.date, *, error_on_missing: Literal[False] | bool) -> TripInstance | None: ...

    def get_trip_instance(self, trip_id: str, date: datetime.date, *, error_on_missing: bool = True) -> TripInstance | None:
        """Gets a trip instance by its trip ID and date

        Parameters
        ----------
        trip_id : str
            The ID of the trip to get the trip instance for.
        date : datetime.date
            The date of the trip instance to get.
        error_on_missing : bool, optional
            Whether to raise an error if the trip instance is missing, defaults to True.

        Returns
        -------
        TripInstance
            The trip instance for the specified trip ID and date.
        """
        result = self._trip_instances_by_date[date].get(trip_id.lower())
        if result is None and error_on_missing:
            raise ValueError(f"Trip instance with ID '{trip_id}' for date '{date}' not found.")
        return result

    def get_stop_times(self, trip_id: str) -> Sequence[StopTime]:
        """Gets all stop times for a trip

        Parameters
        ----------
        trip_id : str
            The ID of the trip to get the stop times for.

        Returns
        -------
        Sequence[StopTime]
            The stop times for the specified trip.
        """
        return self._stop_times_by_trip[trip_id.lower()]

    def get_stop_time_instances(self, trip_id: str, date: datetime.date) -> Sequence[StopTimeInstance]:
        """Gets all stop time instances for a trip on a date

        Parameters
        ----------
        trip_id : str
            The ID of the trip to get the stop time instances for.
        date : datetime.date
            The date to get the stop time instances for.

        Returns
        -------
        Sequence[StopTimeInstance]
            The stop time instances for the specified trip and date.
        """
        return list(self._stop_time_instances_by_date[date].get(trip_id.lower(), {}).values())

    def get_stop_time_instances_between(
        self,
        stop_id: str,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
    ) -> Sequence[StopTimeInstance]:
        """Returns the stop time instances for a stop between two times

        Parameters
        ----------
        stop_id : str
            The ID of the stop to get the stop time instances for.
        start_time : datetime.datetime
            The start time of the range to get the stop time instances for.
        end_time : datetime.datetime
            The end time of the range to get the stop time instances for.

        Returns
        -------
        Sequence[StopTimeInstance]
            The stop time instances for the stop between the two times.
        """
        return sorted(
            (
                stop_time_instance
                for stop_id in self._walk_child_stop_ids(stop_id.lower())
                for stop_time_instance in self._stop_time_instances_by_stop[stop_id.lower()]
                if start_time <= stop_time_instance.actual_departure_time < end_time
            ),
            key=lambda x: x.actual_departure_time,
        )
