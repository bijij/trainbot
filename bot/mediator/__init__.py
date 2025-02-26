from rayquaza import SingleResponseRequest


class ChannelNames:
    GTFS = 'gtfs'


class SearchStopsResult:
    def __init__(self, stops: dict[str, str]):
        self.stops = stops

class SearchStopsRequest(SingleResponseRequest[SearchStopsResult]):
    def __init__(self, query: str):
        self.query = query

class GetStopUrlRequest(SingleResponseRequest[str]):
    def __init__(self, stop_id: str):
        self.stop_id = stop_id
