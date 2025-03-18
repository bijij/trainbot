import datetime
from itertools import islice

from audino import HealthTracker
from malamar import Service
from rapidfuzz import fuzz, process, utils
from rayquaza import Mediator

from ..configuration import Configuration
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
from .store import GtfsDataStore
from .types import Direction, RouteType

__all__ = ("GtfsProvider",)


class GtfsProvider(Service):
    """A service that provides GTFS data to other services via the mediator."""

    def __init__(
        self,
        mediator: Mediator,
        data_store: GtfsDataStore,
        health_tracker: HealthTracker,
        config: Configuration,
    ) -> None:
        """Initializes the GTFS provider.

        Parameters
        ----------
        mediator : Mediator
            The mediator to use for communication.
        data_store : GtfsDataStore
            The GTFS data store to use for data retrieval.
        health_tracker : HealthTracker
            The health tracker to use for tracking the health of the service.
        config : Configuration
            The configuration to use for the service.
        """
        self._mediator = mediator
        self._health_tracker = health_tracker
        self._data_store = data_store
        self._config = config
        super().__init__()

    # region: Mediator message handlers

    async def _handle_search_stops_request(self, request: SearchStopsRequest) -> SearchStopsResult:
        if not await self._health_tracker.get_health(HealthStatusId.GTFS_AVAILABLE):
            raise RuntimeError("GTFS data is currently unavailable.")

        stops = {
            stop: stop.name
            for stop in self._data_store.get_stops_by_route_type(request.route_type)
            if stop.parent_station is None or not request.parent_only
        }
        results = []

        if (
            stop := self._data_store.get_stop(request.query, error_on_missing=False)
        ) is not None and self._data_store.stop_has_route_with_type(stop.id, request.route_type):
            results.append(stop)

        for _, _, stop in process.extract(request.query, stops, scorer=fuzz.WRatio, processor=utils.default_process, limit=request.limit):
            results.append(stop)

        return SearchStopsResult(stops=results[: request.limit])

    async def _handle_get_next_services_request(self, request: GetNextServicesRequest) -> GetNextServicesResult:
        if not await self._health_tracker.get_health(HealthStatusId.GTFS_AVAILABLE):
            raise RuntimeError("GTFS data is currently unavailable.")

        stop = self._data_store.get_stop(request.stop_id)
        lookahead_window = request.time + datetime.timedelta(hours=self._config.lookahead_window[request.route_type])

        services = islice(
            (
                stop_time
                for stop_time in self._data_store.get_stop_time_instances_between(request.stop_id, request.time, lookahead_window)
                if not stop_time.skipped
                and not stop_time.trip.cancelled
                and stop_time.trip.route.type is request.route_type
                and not stop_time.terminates
            ),
            self._config.max_results[request.route_type],
        )

        return GetNextServicesResult(stop, services=list(services))

    async def _handle_get_next_trains_request(self, request: GetNextTrainsRequest) -> GetNextTrainsResult:
        if not await self._health_tracker.get_health(HealthStatusId.GTFS_AVAILABLE):
            raise RuntimeError("GTFS data is currently unavailable.")

        stop = self._data_store.get_stop(request.stop_id)
        now = datetime.datetime.now(datetime.timezone.utc)
        lookahead_window = now + datetime.timedelta(hours=self._config.lookahead_window[RouteType.RAIL])

        down_trains = islice(
            (
                stop_time
                for stop_time in self._data_store.get_stop_time_instances_between(request.stop_id, request.time, lookahead_window)
                if not stop_time.skipped
                and not stop_time.trip.cancelled
                and stop_time.trip.route.type is RouteType.RAIL
                and stop_time.trip.direction is Direction.DOWNWARD
                and not stop_time.terminates
            ),
            self._config.max_results[RouteType.RAIL],
        )
        up_trains = islice(
            (
                stop_time
                for stop_time in self._data_store.get_stop_time_instances_between(request.stop_id, request.time, lookahead_window)
                if not stop_time.skipped
                and not stop_time.trip.cancelled
                and stop_time.trip.route.type is RouteType.RAIL
                and stop_time.trip.direction is Direction.UPWARD
                and not stop_time.terminates
            ),
            self._config.max_results[RouteType.RAIL],
        )

        return GetNextTrainsResult(stop, down_trains=list(down_trains), up_trains=list(up_trains))

    # endregion

    async def start(self, *, timeout: float | None = None) -> None:
        """Starts the GTFS provider.

        Paramters
        ----------
        timeout : float | None
            The maximum time to wait for the service to start.
        """
        self._mediator.create_subscription(ChannelNames.GTFS, SearchStopsRequest, self._handle_search_stops_request)
        self._mediator.create_subscription(ChannelNames.GTFS, GetNextTrainsRequest, self._handle_get_next_trains_request)
        self._mediator.create_subscription(ChannelNames.GTFS, GetNextServicesRequest, self._handle_get_next_services_request)

    async def stop(self, *, timeout: float | None = None) -> None:
        """Stops the GTFS provider.

        Paramters
        ----------
        timeout : float | None
            The maximum time to wait for the service to stop.
        """
        self._mediator.unsubscribe(ChannelNames.GTFS, SearchStopsRequest, self._handle_search_stops_request)
        self._mediator.unsubscribe(ChannelNames.GTFS, GetNextTrainsRequest, self._handle_get_next_trains_request)
        self._mediator.unsubscribe(ChannelNames.GTFS, GetNextServicesRequest, self._handle_get_next_services_request)
