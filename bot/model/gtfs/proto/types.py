from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from google.protobuf.message import Message

if TYPE_CHECKING:

    Incrementality = Literal[0, 1]
    TripScheduleRelationship = Literal[0, 1, 2, 3, 5]
    StopTimeScheduleRelationship = Literal[0, 1, 2, 3]

    class FeedHeader:
        gtfs_realtime_version: str
        incrementality: Incrementality
        timestamp: int | None

    class TripDescriptor:
        trip_id: str | None
        route_id: str | None
        direction_id: int | None
        start_time: str | None
        start_date: str | None
        schedule_relationship: TripScheduleRelationship | None

    class VehicleDescriptor:
        id: str | None
        label: str | None
        license_plate: str | None

    class StopTimeEvent:
        delay: int | None
        time: int | None
        uncertainty: int | None

    class StopTimeUpdate:
        stop_sequence: int | None
        stop_id: str | None
        arrival: StopTimeEvent | None
        departure: StopTimeEvent | None
        schedule_relationship: StopTimeScheduleRelationship

    class TripUpdate:
        trip: TripDescriptor
        vehicle: VehicleDescriptor | None
        stop_time_update: list[StopTimeUpdate]
        timestamp: int | None
        delay: int | None

    class FeedEntity:
        id: str
        is_deleted: bool | None
        trip_update: TripUpdate | None
        # vehicle: VehiclePosition | None
        # alert: Alert | None

    class FeedMessage(Message):
        header: FeedHeader
        entity: list[FeedEntity]

else:
    from .gtfs_realtime_pb2 import *
