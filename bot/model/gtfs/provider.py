import datetime
from difflib import get_close_matches
from itertools import islice

from malamar import Service
from rayquaza import Mediator

from ...mediator import (
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

TRAIN_LOOKAHEAD_HOURS = 4
OTHER_LOOKAHEAD_HOURS = 8
TRAIN_MAX_NEXT_STOPS = 6
OTHER_MAX_NEXT_STOPS = 10


__all__ = ("GtfsProvider",)


MAX_RESULTS = 25


class GtfsProvider(Service):

    def __init__(self, mediator: Mediator, data_store: GtfsDataStore) -> None:
        self.mediator = mediator
        self.data_store = data_store
        super().__init__()

    # region: Mediator message handlers

    async def handle_search_stops_request(self, request: SearchStopsRequest) -> SearchStopsResult:
        stops = self.data_store.get_stops_by_route_type(request.route_type)

        if request.query:
            name_map = {stop.name: stop for stop in stops}
            stops_names = get_close_matches(request.query, name_map, cutoff=0.1)
            stops = [name_map[name] for name in stops_names]

        if request.parent_only:
            stops = [stop for stop in stops if stop.parent_stop is None]

        return SearchStopsResult(stops=stops[:MAX_RESULTS])

    async def handle_get_next_services_request(self, request: GetNextServicesRequest) -> GetNextServicesResult:
        stop = self.data_store.get_stop(request.stop_id)
        lookahead_window = request.time + datetime.timedelta(hours=OTHER_LOOKAHEAD_HOURS)

        services = islice(
            (
                stop_time
                for stop_time in self.data_store.get_stop_time_instances_between(request.stop_id, request.time, lookahead_window)
                if not stop_time.skipped
                and not stop_time.trip.cancelled
                and stop_time.trip.route.type is request.route_type
                and not stop_time.terminates
            ),
            OTHER_MAX_NEXT_STOPS,
        )

        return GetNextServicesResult(stop, services=list(services))

    async def handle_get_next_trains_request(self, request: GetNextTrainsRequest) -> GetNextTrainsResult:
        stop = self.data_store.get_stop(request.stop_id)
        now = datetime.datetime.now(datetime.timezone.utc)
        lookahead_window = now + datetime.timedelta(hours=TRAIN_LOOKAHEAD_HOURS)

        down_trains = islice(
            (
                stop_time
                for stop_time in self.data_store.get_stop_time_instances_between(request.stop_id, request.time, lookahead_window)
                if not stop_time.skipped
                and not stop_time.trip.cancelled
                and stop_time.trip.route.type is RouteType.RAIL
                and stop_time.trip.direction is Direction.DOWNWARD
                and not stop_time.terminates
            ),
            TRAIN_MAX_NEXT_STOPS,
        )
        up_trains = islice(
            (
                stop_time
                for stop_time in self.data_store.get_stop_time_instances_between(request.stop_id, request.time, lookahead_window)
                if not stop_time.skipped
                and not stop_time.trip.cancelled
                and stop_time.trip.route.type is RouteType.RAIL
                and stop_time.trip.direction is Direction.UPWARD
                and not stop_time.terminates
            ),
            TRAIN_MAX_NEXT_STOPS,
        )

        return GetNextTrainsResult(stop, down_trains=list(down_trains), up_trains=list(up_trains))

    # endregion

    async def start(self, *, timeout: float | None = None) -> None:
        self.mediator.create_subscription(ChannelNames.GTFS, SearchStopsRequest, self.handle_search_stops_request)
        self.mediator.create_subscription(ChannelNames.GTFS, GetNextTrainsRequest, self.handle_get_next_trains_request)
        self.mediator.create_subscription(ChannelNames.GTFS, GetNextServicesRequest, self.handle_get_next_services_request)

    async def stop(self, *, timeout: float | None = None) -> None:
        self.mediator.unsubscribe(ChannelNames.GTFS, SearchStopsRequest, self.handle_search_stops_request)
        self.mediator.unsubscribe(ChannelNames.GTFS, GetNextTrainsRequest, self.handle_get_next_trains_request)
        self.mediator.unsubscribe(ChannelNames.GTFS, GetNextServicesRequest, self.handle_get_next_services_request)
