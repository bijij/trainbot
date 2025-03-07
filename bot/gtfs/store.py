import datetime
from asyncio import Lock
from collections import defaultdict
from collections.abc import Sequence

from ..configuration import Configuration
from .types import Route, RouteType, Service, Stop, StopTime, StopTimeInstance, Trip, TripInstance

__all__ = ("GtfsDataStore",)


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
        self._lock = Lock()
        self._config = config

        # Static data
        self._routes: dict[str, Route] = {}
        self._services: dict[str, Service] = {}
        self._trips: dict[str, Trip] = {}
        self._trips_by_route: dict[str, list[Trip]] = defaultdict(list)
        self._trips_by_service: dict[str, list[Trip]] = defaultdict(list)
        self._stops: dict[str, Stop] = {}
        self._stop_times_by_trip: dict[str, list[StopTime]] = defaultdict(list)
        self._stop_times_by_stop: dict[str, list[StopTime]] = defaultdict(list)
        self._route_types_by_stop: dict[str, set[RouteType]] = defaultdict(set)

        # Real-time data
        self._trip_instances_by_date: dict[datetime.date, dict[str, TripInstance]] = defaultdict(dict)
        self._stop_time_instances_by_date: dict[datetime.date, dict[str, dict[int, StopTimeInstance]]] = defaultdict(
            lambda: defaultdict(dict)
        )
        self._stop_time_instances_by_stop: dict[str, list[StopTimeInstance]] = defaultdict(list)

    async def clear(self) -> None:
        """Clears all data from the data store."""
        async with self._lock:
            self._routes.clear()
            self._services.clear()
            self._trips.clear()
            self._trips_by_route.clear()
            self._trips_by_service.clear()
            self._stops.clear()
            self._stop_times_by_trip.clear()
            self._stop_times_by_stop.clear()
            self._trip_instances_by_date.clear()
            self._stop_time_instances_by_date.clear()
            self._stop_time_instances_by_stop.clear()

    async def add_route(self, route: Route) -> None:
        """Adds a route to the data store and updates the route instances.

        Parameters
        ----------
        route : Route
            The route to add to the data store.
        """
        async with self._lock:
            self._routes[route.id] = route.register(self)

    async def add_service(self, service: Service) -> None:
        """Adds a service to the data store and updates the service instances.

        Parameters
        ----------
        service : Service
            The service to add to the data store.
        """
        async with self._lock:
            self._services[service.id] = service.register(self)

    async def add_trip(self, trip: Trip) -> None:
        """Adds a trip to the data store and updates the trip instances.

        Parameters
        ----------
        trip : Trip
            The trip to add to the data store.
        """
        async with self._lock:
            self._trips[trip.id] = trip.register(self)
            self._trips_by_route[trip.route.id].append(trip)
            self._trips_by_service[trip.service.id].append(trip)

    async def add_stop(self, stop: Stop) -> None:
        """Adds a stop to the data store and updates the stop instances.

        Parameters
        ----------
        stop : Stop
            The stop to add to the data store.
        """
        async with self._lock:
            self._stops[stop.id] = stop.register(self)

    async def add_stop_time(self, stop_time: StopTime) -> None:
        """Adds a stop time to the data store and updates the stop time instances.

        Parameters
        ----------
        stop_time : StopTime
            The stop time to add to the data store.
        """
        async with self._lock:
            stop_time = stop_time.register(self)

            route_type = self._routes[stop_time.trip.route.id].type
            self._stop_times_by_trip[stop_time.trip.id].append(stop_time)
            self._route_types_by_stop[stop_time.stop.id].add(route_type)
            stop = stop_time.stop
            while stop is not None:
                self._stop_times_by_stop[stop.id].append(stop_time)
                self._route_types_by_stop[stop.id].add(route_type)
                stop = self._stops.get(stop.parent_stop_id or "")

    async def remove_old_trip_instances(self) -> None:
        """Removes trip instances for dates older than yesterday."""
        async with self._lock:
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

    async def create_trip_instances(self) -> None:
        """Creates the trip instances for yesterday, today, and tomorrow."""
        async with self._lock:
            today = datetime.date.today()
            yesterday = today - datetime.timedelta(days=1)
            tomorrow = today + datetime.timedelta(days=1)

            dates = [yesterday, today, tomorrow]
            for date in dates:
                if not self._trip_instances_by_date[date]:
                    for trip in self._trips.values():
                        service = self._services[trip.service.id]
                        if service.runs_on(date):
                            self._trip_instances_by_date[date][trip.id] = TripInstance(trip, date).register(self)
                            for stop_time in self._stop_times_by_trip[trip.id]:
                                self._stop_time_instances_by_date[date][trip.id][stop_time.sequence] = StopTimeInstance(
                                    stop_time, date
                                ).register(self)

                    for stop_time_instances in self._stop_time_instances_by_date[date].values():
                        for stop_time_instance in stop_time_instances.values():
                            stop = stop_time_instance.stop
                            while stop is not None:
                                self._stop_time_instances_by_stop[stop.id].append(stop_time_instance)
                                stop = self._stops.get(stop.parent_stop_id or "")

    async def set_trip_instance_status(self, trip_id: str, date: datetime.date, cancelled: bool) -> None:
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
        async with self._lock:
            self._trip_instances_by_date[date][trip_id].cancelled = cancelled

    async def set_stop_time_instance_status(self, trip_id: str, date: datetime.date, stop_sequence: int, skipped: bool) -> None:
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
        async with self._lock:
            self._stop_time_instances_by_date[date][trip_id][stop_sequence].skipped = skipped

    async def set_stop_time_actual_arrival_time(
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
        async with self._lock:
            self._stop_time_instances_by_date[date][trip_id][stop_sequence]._actual_arrival_time = arrival_time

    async def set_stop_time_actual_departure_time(
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
        async with self._lock:
            self._stop_time_instances_by_date[date][trip_id][stop_sequence]._actual_departure_time = departure_time

    def get_route(self, route_id: str) -> Route:
        """Gets a route by its ID

        Parameters
        ----------
        route_id : str
            The ID of the route to get.

        Returns
        -------
        Route
            The route with the specified ID.
        """
        return self._routes[route_id]

    def get_service(self, service_id: str) -> Service:
        """Gets a service by its ID

        Parameters
        ----------
        service_id : str
            The ID of the service to get.

        Returns
        -------
        Service
            The service with the specified ID.
        """
        return self._services[service_id]

    def get_trip(self, trip_id: str) -> Trip:
        """Gets a trip by its ID

        Parameters
        ----------
        trip_id : str
            The ID of the trip to get.

        Returns
        -------
        Trip
            The trip with the specified ID.
        """
        return self._trips[trip_id]

    def get_stop(self, stop_id: str) -> Stop:
        """Gets a stop by its ID

        Parameters
        ----------
        stop_id : str
            The ID of the stop to get.

        Returns
        -------
        Stop
            The stop with the specified ID.
        """
        return self._stops[stop_id]

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
        return [stop for stop in self._stops.values() if route_type in self._route_types_by_stop[stop.id]]

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
        return self._trips_by_route[route_id]

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
        return self._trips_by_service[service_id]

    def get_trip_instance(self, trip_id: str, date: datetime.date) -> TripInstance:
        """Gets a trip instance by its trip ID and date

        Parameters
        ----------
        trip_id : str
            The ID of the trip to get the trip instance for.
        date : datetime.date
            The date of the trip instance to get.

        Returns
        -------
        TripInstance
            The trip instance for the specified trip ID and date.
        """
        return self._trip_instances_by_date[date][trip_id]

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
        return self._stop_times_by_trip[trip_id]

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
        return list(self._stop_time_instances_by_date[date][trip_id].values())

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
                for stop_time_instance in self._stop_time_instances_by_stop[stop_id]
                if start_time <= stop_time_instance.actual_departure_time < end_time
            ),
            key=lambda x: x.actual_departure_time,
        )
