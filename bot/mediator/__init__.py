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
    """The names of the mediator channels used by each service."""

    GTFS = "gtfs"


# region: Search Stops


class SearchStopsResult(NamedTuple):
    """GTFS stop search results.

    Attributes
    ----------
    stops : list[Stop]
        The stops that match the search query.
    """

    stops: list[Stop]


class SearchStopsRequest(SingleResponseRequest[SearchStopsResult]):
    """Represents a request to search for GTFS stops.

    Attributes
    ----------
    query : str
        The search query to use.
    route_type : RouteType
        The route type to search for.
    parent_only : bool
        Whether to only return parent stops.
    limit : int | None
        The maximum number of results to return.
    """

    def __init__(self, query: str, route_type: RouteType, parent_only: bool = False, limit: int | None = None):
        """Initializes the search stops request.

        Parameters
        ----------
        query : str
            The search query to use.
        route_type : RouteType
            The route type to search for.
        parent_only : bool, optional
            Whether to only return parent stops, by default False.
        limit : int | None, optional
            The maximum number of results to return, by default None.
        """
        self.query: str = query
        self.route_type: RouteType = route_type
        self.parent_only: bool = parent_only
        self.limit: int | None = limit


# endregion


# region: Get Next Services


class GetNextServicesResult(NamedTuple):
    """The result of a request to get the next services for a stop.

    Attributes
    ----------
    stop : Stop
        The stop for which services were retrieved.
    services : list[StopTimeInstance]
        The next services for the stop, ordered by estimated departure time.
    """

    stop: Stop
    services: list[StopTimeInstance]


class GetNextServicesRequest(SingleResponseRequest[GetNextServicesResult]):
    """Represents a request to get the next services for a stop."

    Attributes
    ----------
    stop_id : str
        The ID of the stop to retrieve services for.
    time : datetime.datetime
        The time to use for the search.
    route_type : RouteType
        The route type to search for.
    """

    def __init__(self, stop_id: str, time: datetime.datetime, route_type: RouteType, max_results: int):
        """Initializes the get next services request."

        Parameters
        ----------
        stop_id : str
            The ID of the stop to retrieve services for.
        time : datetime.datetime
            The time to use for the search.
        route_type : RouteType
            The route type to search for.
        max_results : int
            The maximum number of results to return.
        """
        self.stop_id: str = stop_id
        self.time: datetime.datetime = time
        self.route_type: RouteType = route_type
        self.max_results: int = max_results


# region: Get Next Trains
class GetNextTrainsResult(NamedTuple):
    """The result of a request to get the next trains for a stop.

    Attributes
    ----------
    stop : Stop
        The stop for which trains were retrieved.
    down_trains : list[StopTimeInstance]
        The next downward trains for the stop, ordered by estimated departure time.
    up_trains : list[StopTimeInstance]
        The next upward trains for the stop, ordered by estimated departure time.
    """

    stop: Stop
    down_trains: list[StopTimeInstance]
    up_trains: list[StopTimeInstance]


class GetNextTrainsRequest(SingleResponseRequest[GetNextTrainsResult]):
    """Represents a request to get the next trains for a stop.

    Attributes
    ----------
    stop_id : str
        The ID of the stop to retrieve trains for.
    time : datetime.datetime
        The time to use for the search.
    """

    def __init__(self, stop_id: str, time: datetime.datetime, max_results: int):
        """Initializes the get next trains request.

        Parameters
        ----------
        stop_id : str
            The ID of the stop to retrieve trains for.
        time : datetime.datetime
            The time to use for the search.
        max_results : int
            The maximum number of results to return.
        """
        self.stop_id: str = stop_id
        self.time: datetime.datetime = time
        self.max_results: int = max_results


# endregion
