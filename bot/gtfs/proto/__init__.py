from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from google.protobuf.message import Message

if TYPE_CHECKING:

    Incrementality = Literal[0, 1]
    TripScheduleRelationship = Literal[0, 1, 2, 3, 5]
    StopTimeScheduleRelationship = Literal[0, 1, 2, 3]

    class FeedHeader:
        """Represents the header of a GTFS-realtime message.

        Attributes
        ----------
        gtfs_realtime_version : str
            The version of the GTFS-realtime protocol.
        incrementality : Incrementality
            The incrementality of the message.
        timestamp : int | None
            The timestamp of the message.
        """

        gtfs_realtime_version: str
        incrementality: Incrementality
        timestamp: int | None

    class TripDescriptor:
        """Descriptor used to refer to a trip.

        Attributes
        ----------
        trip_id : str | None
            The ID of the trip.
        route_id : str | None
            The ID of the route.
        direction_id : int | None
            The direction of the trip.
        start_time : str | None
            The start time of the trip.
        start_date : str | None
            The start date of the trip.
        schedule_relationship : TripScheduleRelationship | None
                The relationship between the trip and the static GTFS schedule data.
        """

        trip_id: str | None
        route_id: str | None
        direction_id: int | None
        start_time: str | None
        start_date: str | None
        schedule_relationship: TripScheduleRelationship | None

    class VehicleDescriptor:
        """Descriptor used to refer to a vehicle.

        Attributes
        ----------
        id : str | None
            The ID of the vehicle.
        label : str | None
            The label of the vehicle.
        license_plate : str | None
            The license plate of the vehicle.
        """

        id: str | None
        label: str | None
        license_plate: str | None

    class StopTimeEvent:
        """Represents an arrival or departure event at a stop.

        Attributes
        ----------
        delay : int | None
            The delay of the event in seconds.
        time : int | None
            The time of the event in seconds since 1970-01-01 00:00:00 UTC.
        uncertainty : int | None
            The uncertainty of the event in seconds.
        """

        delay: int | None
        time: int | None
        uncertainty: int | None

    class StopTimeUpdate:
        """Represents an update to a stop time.

        Attributes
        ----------
        stop_sequence : int | None
            The sequence number of the stop.
        stop_id : str | None
            The ID of the stop.
        arrival : StopTimeEvent | None
            The arrival event at the stop.
        departure : StopTimeEvent | None
            The departure event from the stop.
        schedule_relationship : StopTimeScheduleRelationship
            The relationship between the stop time and the static GTFS schedule data.
        """

        stop_sequence: int | None
        stop_id: str | None
        arrival: StopTimeEvent | None
        departure: StopTimeEvent | None
        schedule_relationship: StopTimeScheduleRelationship

    class TripUpdate:
        """Represents an update to a trip.

        Attributes
        ----------
        trip : TripDescriptor
            The descriptor of the trip.
        vehicle : VehicleDescriptor | None
            The descriptor of the vehicle.
        stop_time_update : list[StopTimeUpdate]
            The list of updates to the stop times.
        timestamp : int | None
            The timestamp of the message in seconds since 1970-01-01 00:00:00 UTC.
        delay : int | None
            The delay of the trip in seconds.
        """

        trip: TripDescriptor
        vehicle: VehicleDescriptor | None
        stop_time_update: list[StopTimeUpdate]
        timestamp: int | None
        delay: int | None

    class FeedEntity:
        """Represents an entity in a GTFS-realtime message.

        Attributes
        ----------
        id : str
            The ID of the entity.
        is_deleted : bool | None
            Whether the entity is deleted.
        trip_update : TripUpdate | None
            The update to the trip.
        """

        id: str
        is_deleted: bool | None
        trip_update: TripUpdate | None
        # vehicle: VehiclePosition | None
        # alert: Alert | None

    class FeedMessage(Message):
        """Represents a GTFS-realtime message.

        Attributes
        ----------
        header : FeedHeader
            The header of the message.
        entity : list[FeedEntity]
            The list of entities in the message.
        """

        header: FeedHeader
        entity: list[FeedEntity]

else:
    from .gtfs_realtime_pb2 import *
