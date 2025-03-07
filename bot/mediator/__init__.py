from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, NamedTuple

from rayquaza import SingleResponseRequest

if TYPE_CHECKING:
    from ..gtfs.types import RouteType, Stop, StopTimeInstance


__all__ = (
    "ChannelNames",
    "SearchStopsRequest",
    "SearchStopsResult",
    "GetNextServicesRequest",
    "GetNextServicesResult",
    "GetNextTrainsRequest",
    "GetNextTrainsResult",
)


class ChannelNames:
    GTFS = "gtfs"


# region: Search Stops


class SearchStopsResult(NamedTuple):
    stops: list[Stop]


class SearchStopsRequest(SingleResponseRequest[SearchStopsResult]):
    def __init__(self, query: str, route_type: RouteType, parent_only: bool = False):
        self.query: str = query
        self.route_type: RouteType = route_type
        self.parent_only: bool = parent_only


# endregion


# region: Get Next Services


class GetNextServicesResult(NamedTuple):
    stop: Stop
    services: list[StopTimeInstance]


class GetNextServicesRequest(SingleResponseRequest[GetNextServicesResult]):
    def __init__(self, stop_id: str, time: datetime.datetime, route_type: RouteType):
        self.stop_id: str = stop_id
        self.time: datetime.datetime = time
        self.route_type: RouteType = route_type


# region: Get Next Trains
class GetNextTrainsResult(NamedTuple):
    stop: Stop
    down_trains: list[StopTimeInstance]
    up_trains: list[StopTimeInstance]


class GetNextTrainsRequest(SingleResponseRequest[GetNextTrainsResult]):
    def __init__(self, stop_id: str, time: datetime.datetime):
        self.stop_id: str = stop_id
        self.time: datetime.datetime = time


# endregion
