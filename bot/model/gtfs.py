import csv
import io
import zipfile
from collections import defaultdict
from difflib import get_close_matches

import aiohttp
from audino import HealthTracker
from malamar import Service
from rayquaza import Mediator

from ..health import HealthStatusId
from ..mediator import ChannelNames, GetStopUrlRequest, SearchStopsRequest, SearchStopsResult

GTFS_ZIP = "https://gtfsrt.api.translink.com.au/GTFS/SEQ_GTFS.zip"


# HACK: This currently stores the stop ID to name and URL mapping in memory
#       as the rest of the data isn't needed yet
STOPS: dict[str, tuple[str, str]] = {}

STOP_IDS_BY_NAME: dict[str, set[str]] = defaultdict(set)


class Gtfs(Service):

    def __init__(self, *, health_tracker: HealthTracker, mediator: Mediator) -> None:
        self.health_tracker = health_tracker
        self.mediator = mediator
        super().__init__()

    async def load_stops(self) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.get(GTFS_ZIP) as response:
                data = io.BytesIO(await response.read())
                # Extract stops from GTFS
                zip = zipfile.ZipFile(data)

                with zip.open("stops.txt") as f:
                    reader = csv.DictReader(io.TextIOWrapper(f, "utf-8"))
                    for row in reader:
                        STOPS[row["stop_id"]] = (row["stop_name"], row["stop_url"])
                        STOP_IDS_BY_NAME[row["stop_name"].lower()].add(row["stop_id"])

        await self.health_tracker.set_health(HealthStatusId.GTFS_AVAILABLE, True)
        print(f'Successfully loaded GTFS data ({len(STOPS)} stops)')

    async def search_stops(self, request: SearchStopsRequest) -> SearchStopsResult:
        MAX_RESULTS = 25
        matches = []
        
        for match in get_close_matches(request.query.lower(), STOP_IDS_BY_NAME.keys(), n=MAX_RESULTS, cutoff=0.1):
            for stop_id in STOP_IDS_BY_NAME[match]:
                matches.append((stop_id, STOPS[stop_id][0]))

        print('Returning', len(matches), 'results for', request.query)

        return SearchStopsResult({stop_id: name for stop_id, name in matches[:MAX_RESULTS]})

    async def get_stop_url(self, request: GetStopUrlRequest) -> str:
        return STOPS[request.stop_id][1]

    async def start(self, *, timeout: float | None = None) -> None:
        self.mediator.create_subscription(
            ChannelNames.GTFS, SearchStopsRequest, self.search_stops
        )

        self.mediator.create_subscription(
            ChannelNames.GTFS, GetStopUrlRequest, self.get_stop_url
        )

        await self.load_stops()

    async def stop(self, *, timeout: float | None = None) -> None: ...
