from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from rayquaza import SingleResponseRequest

if TYPE_CHECKING:
    from ..model.gtfs import RouteType, Stop, StopTimeInstance


class ChannelNames:
    GTFS = "gtfs"


# region: Search Stops


class SearchStopsResult(NamedTuple):
    stops: list[Stop]


class SearchStopsRequest(SingleResponseRequest[SearchStopsResult]):
    def __init__(self, query: str, route_type: RouteType):
        self.query: str = query
        self.route_type: RouteType = route_type


# endregion


# region: Get Next Services


class GetNextServicesResult(NamedTuple):
    stop: Stop
    services: list[StopTimeInstance]


class GetNextServicesRequest(SingleResponseRequest[GetNextServicesResult]):
    def __init__(self, stop_id: str, route_type: RouteType):
        self.stop_id: str = stop_id
        self.route_type: RouteType = route_type


# region: Get Next Trains
class GetNextTrainsResult(NamedTuple):
    stop: Stop
    down_trains: list[StopTimeInstance]
    up_trains: list[StopTimeInstance]


class GetNextTrainsRequest(SingleResponseRequest[GetNextTrainsResult]):
    def __init__(self, stop_id: str):
        self.stop_id: str = stop_id


# endregion
