import datetime
from collections.abc import Mapping, Sequence
from enum import Enum, Flag, auto
from random import choice
from typing import Literal, Self, overload

from ...gtfs.types import Direction, Route, RouteType, Stop, StopTimeInstance

ANSI_ESCAPE = "\033[0;"
ANSI_RESET = f"{ANSI_ESCAPE}0m"
ZWSP = "\u200b"

ANSI_FORMATING = {...}


class DiscordAnsiColour(Enum):
    """Represents the colours that can be used in Discord messages."""

    GREY = auto()
    RED = auto()
    YELLOW = auto()
    GREEN = auto()
    CYAN = auto()
    BLUE = auto()
    MAGENTA = auto()
    WHITE = auto()

    @classmethod
    def from_colour(cls, colour: str) -> Self:
        """Returns the colour code for the colour.

        Parameters
        ----------
        colour : str
            The colour to get the code for.

        Returns
        -------
        DiscordAnsiColour
            The colour code for the colour.
        """
        r, g, b = int(colour[:2], 16), int(colour[2:4], 16), int(colour[4:], 16)

        # Find the closest colour
        closest = cls.GREY
        closest_distance = float("inf")
        for discord_colour, rgb in COLOUR_MAP.items():
            distance = sum((a - b) ** 2 for a, b in zip(rgb, (r, g, b)))
            if distance < closest_distance:
                closest = discord_colour
                closest_distance = distance

        return closest  # type: ignore

    @classmethod
    def from_route(cls, route: Route) -> Self:
        """Returns the colour code for the route.

        Parameters
        ----------
        route : Route
            The route to get the colour for.

        Returns
        -------
        DiscordAnsiColour
            The colour code for the route.
        """
        if route.type is RouteType.RAIL:
            short_name = route.short_name[-2:]
        else:
            short_name = route.short_name

        return ROUTE_COLOURS.get(route.type, {}).get(short_name, cls.from_colour(route.colour))  # type: ignore

    @property
    def code(self) -> str:
        """Returns the ANSI code for the colour."""
        return COLOUR_CODES[self]


COLOUR_MAP = {
    DiscordAnsiColour.GREY: (0x40, 0x40, 0x40),
    DiscordAnsiColour.RED: (0xFF, 0x00, 0x00),
    DiscordAnsiColour.YELLOW: (0xFF, 0xFF, 0x00),
    DiscordAnsiColour.GREEN: (0x00, 0xFF, 0x00),
    DiscordAnsiColour.CYAN: (0x00, 0xFF, 0xFF),
    DiscordAnsiColour.BLUE: (0x00, 0x00, 0xFF),
    DiscordAnsiColour.MAGENTA: (0xFF, 0x00, 0xFF),
    DiscordAnsiColour.WHITE: (0xFF, 0xFF, 0xFF),
}


ROUTE_COLOURS = {
    RouteType.RAIL: {
        "GY": DiscordAnsiColour.GREEN,
        "NA": DiscordAnsiColour.GREEN,
        "CA": DiscordAnsiColour.GREEN,
        "RP": DiscordAnsiColour.CYAN,
        "SH": DiscordAnsiColour.BLUE,
        "BD": DiscordAnsiColour.YELLOW,
        "DB": DiscordAnsiColour.MAGENTA,
        "FG": DiscordAnsiColour.RED,
        "BR": DiscordAnsiColour.GREY,
        "CL": DiscordAnsiColour.BLUE,
        "BN": DiscordAnsiColour.RED,
        "VL": DiscordAnsiColour.YELLOW,
        "SP": DiscordAnsiColour.CYAN,
        "IP": DiscordAnsiColour.GREEN,
        "RW": DiscordAnsiColour.GREEN,
    },
    RouteType.BUS: {
        "M1": DiscordAnsiColour.BLUE,
        "M2": DiscordAnsiColour.BLUE,
        "30": DiscordAnsiColour.YELLOW,
        "40": DiscordAnsiColour.RED,
        "50": DiscordAnsiColour.RED,
        "60": DiscordAnsiColour.BLUE,
        "61": DiscordAnsiColour.RED,
        "66": DiscordAnsiColour.BLUE,
    },
    RouteType.FERRY: {
        "F1": DiscordAnsiColour.BLUE,
        "F11": DiscordAnsiColour.GREEN,
        "F12": DiscordAnsiColour.MAGENTA,
        "F21": DiscordAnsiColour.CYAN,
        "F22": DiscordAnsiColour.YELLOW,
        "F23": DiscordAnsiColour.RED,
        "F24": DiscordAnsiColour.GREEN,
    },
}


COLOUR_CODES = {
    DiscordAnsiColour.GREY: "30",
    DiscordAnsiColour.RED: "31",
    DiscordAnsiColour.GREEN: "32",
    DiscordAnsiColour.YELLOW: "33",
    DiscordAnsiColour.BLUE: "34",
    DiscordAnsiColour.MAGENTA: "35",
    DiscordAnsiColour.CYAN: "36",
    DiscordAnsiColour.WHITE: "37",
}


SCREEN_WIDTH = 48
MAX_NEXT_TRAINS = 6


def _with_formatting(text: str, colour: DiscordAnsiColour | None = None, bold: bool = False, underline: bool = False) -> str:
    """Formats text with ANSI escape codes.

    Parameters
    ----------
    text : str
        The text to format.
    colour : Colour, optional
        The colour of the text.
    bold : bool, optional
        Whether the text should be bold.
    underline : bool, optional
        Whether the text should be underlined.

    Returns
    -------
    str
        The formatted text.
    """

    codes = []

    if colour is not None:
        codes.append(colour.code)

    if bold:
        codes.append("1")
    if underline:
        codes.append("4")

    return f"{ANSI_ESCAPE}{";".join(codes)}m{text.rstrip()}{ANSI_RESET}"


class _Line(Flag):
    NONE = 0
    NORTH_COAST = 0x1
    KIPPA_RING = 0x2
    SHORNCLIFFE = 0x4
    AIRPORT = 0x8
    DOOMBEN = 0x10
    FERNY_GROVE = 0x20
    INNER_CITY = 0x40
    CLEVELAND = 0x80
    GOLD_COAST = 0x100
    SPRINGFIELD = 0x200
    ROSEWOOD = 0x400


NORTHSIDE = _Line.NORTH_COAST | _Line.KIPPA_RING | _Line.SHORNCLIFFE | _Line.AIRPORT | _Line.DOOMBEN | _Line.FERNY_GROVE
SOUTHSIDE = _Line.CLEVELAND | _Line.GOLD_COAST | _Line.SPRINGFIELD | _Line.ROSEWOOD


class _Orientation(Flag):
    NONE = 0
    NORTH = 0x1
    SOUTH = 0x2
    EAST = 0x4
    WEST = 0x8


OUTBOUND_DIRECTIONS = {
    _Line.NORTH_COAST: _Orientation.NORTH,
    _Line.KIPPA_RING: _Orientation.NORTH,
    _Line.SHORNCLIFFE: _Orientation.NORTH,
    _Line.AIRPORT: _Orientation.NORTH,
    _Line.DOOMBEN: _Orientation.EAST,
    _Line.FERNY_GROVE: _Orientation.NORTH,
    _Line.CLEVELAND: _Orientation.SOUTH | _Orientation.EAST,
    _Line.GOLD_COAST: _Orientation.SOUTH,
    _Line.SPRINGFIELD: _Orientation.SOUTH,
    _Line.ROSEWOOD: _Orientation.WEST,
}


END_OF_LINE = {
    "place_gymsta",  # Gympie North
    "place_kprsta",  # Kippa-Ring
    "place_shnsta",  # Shorncliffe
    "place_intsta",  # International Airport
    "place_dbnsta",  # Doomben
    "place_fersta",  # Ferny Grove
    "place_clesta",  # Cleveland
    "place_varsta",  # Varsity Lakes
    "place_spcsta",  # Springfield Central
    "place_rossta",  # Rosewood
}


def _get_header_text(stop_id: str, slim: bool = False) -> Mapping[Direction, str]:
    """Returns the header text for a train timetable.

    Parameters
    ----------
    line : _Line
        The line to get the header text for.

    Returns
    -------
    Mapping[Direction, str]
        The header text for the line for each direction.
    """
    line = LINES[stop_id.lower()]

    if line is _Line.INNER_CITY:
        if slim:
            return {Direction.UPWARD: "South/West", Direction.DOWNWARD: "North"}
        return {Direction.UPWARD: "(1-6) South/West", Direction.DOWNWARD: "(1-6) North"}

    outbound_orientation = _Orientation.NONE
    for line_ in _Line:
        if line & line_:
            outbound_orientation |= OUTBOUND_DIRECTIONS[line_]

    outbound_orientation_text = "/".join(
        orientation.name.title() for orientation in _Orientation if outbound_orientation & orientation  # type: ignore
    )

    if line & NORTHSIDE:
        upward_text = "City & South/West"
        downward_text = outbound_orientation_text
    else:
        downward_text = "City & North"
        upward_text = outbound_orientation_text

    return {Direction.DOWNWARD: downward_text, Direction.UPWARD: upward_text}


# TODO: Figure out how to do this without hardcoding the stop IDs


def _get_inbound_direction(stop_id: str) -> Direction:
    """Returns the inbound direction for a stop.

    Parameters
    ----------
    stop_id : str
        The stop ID.

    Returns
    -------
    Direction
        The inbound direction.
    """
    line = LINES[stop_id.lower()]

    if line & NORTHSIDE:
        return Direction.UPWARD
    else:
        return Direction.DOWNWARD


LINES = {
    # fmt: off
    "place_albsta": _Line.NORTH_COAST | _Line.KIPPA_RING | _Line.SHORNCLIFFE | _Line.AIRPORT | _Line.DOOMBEN,  # Albion
    "place_aldsta": _Line.FERNY_GROVE,  # Alderley
    "place_altsta": _Line.GOLD_COAST,  # Altandi
    "place_ascsta": _Line.DOOMBEN,  # Ascot
    "place_aucsta": _Line.ROSEWOOD | _Line.SPRINGFIELD,  # Auchenflower
    "place_balsta": _Line.NORTH_COAST | _Line.KIPPA_RING,  # Bald Hills
    "place_bansta": _Line.GOLD_COAST,  # Banoon
    "place_beesta": _Line.GOLD_COAST,  # Beenleigh
    "place_bbrsta": _Line.NORTH_COAST,  # Beerburrum
    "place_bwrsta": _Line.NORTH_COAST,  # Beerwah
    "place_betsta": _Line.GOLD_COAST,  # Bethania
    "place_binsta": _Line.SHORNCLIFFE,  # Bindha
    "place_birsta": _Line.CLEVELAND,  # Birkdale
    "place_parsta": _Line.CLEVELAND | _Line.GOLD_COAST,  # Boggo Road/Park Road
    "place_bdlsta": _Line.SHORNCLIFFE,  # Boondall
    "place_bvlsta": _Line.ROSEWOOD,  # Booval
    "place_bowsta": _Line.NORTH_COAST | _Line.KIPPA_RING| _Line.SHORNCLIFFE | _Line.AIRPORT| _Line.DOOMBEN | _Line.FERNY_GROVE,  # Bowen Hills
    "place_brasta": _Line.NORTH_COAST | _Line.KIPPA_RING,  # Bray Park
    "place_bunsta": _Line.ROSEWOOD,  # Bundamba
    "place_bursta": _Line.NORTH_COAST,  # Burpengary
    "place_cabstn": _Line.NORTH_COAST,  # Caboolture
    "place_cansta": _Line.CLEVELAND,  # Cannon Hill
    "place_cassta": _Line.NORTH_COAST | _Line.KIPPA_RING,  # Carseldine
    "place_censta": _Line.INNER_CITY,  # Central
    "place_chesta": _Line.ROSEWOOD | _Line.SPRINGFIELD,  # Chelmer
    "place_clasta": _Line.DOOMBEN,  # Clayfield
    "place_clesta": _Line.CLEVELAND,  # Cleveland
    "place_cmrstn": _Line.GOLD_COAST,  # Coomera
    "place_cppsta": _Line.GOLD_COAST,  # Coopers Plains
    "place_crnsta": _Line.NORTH_COAST,  # Cooran
    "place_crysta": _Line.NORTH_COAST,  # Cooroy
    "place_coosta": _Line.CLEVELAND,  # Coorparoo
    "place_corsta": _Line.ROSEWOOD | _Line.SPRINGFIELD,  # Corinda
    "place_daksta": _Line.NORTH_COAST,  # Dakabin
    "place_darsta": _Line.ROSEWOOD | _Line.SPRINGFIELD,  # Darra
    "place_deasta": _Line.SPRINGFIELD,  # Deagon
    "place_dinsta": _Line.ROSEWOOD,  # Dinmore
    "place_domsta": _Line.AIRPORT,  # Domestic Airport
    "place_dbnsta": _Line.DOOMBEN,  # Doomben
    "place_dupsta": _Line.GOLD_COAST,  # Dutton Park
    "place_egjsta": _Line.NORTH_COAST | _Line.KIPPA_RING | _Line.SHORNCLIFFE | _Line.AIRPORT | _Line.DOOMBEN,  # Eagle Junction
    "place_eassta": _Line.ROSEWOOD,  # East Ipswich
    "place_ebbsta": _Line.ROSEWOOD,  # Ebbw Vale
    "place_edesta": _Line.GOLD_COAST,  # Edens Landing
    "place_elmsta": _Line.NORTH_COAST,  # Elimbah
    "place_enosta": _Line.FERNY_GROVE,  # Enoggera
    "place_eudsta": _Line.NORTH_COAST,  # Eudlo
    "place_eumsta": _Line.NORTH_COAST,  # Eumundi
    "place_faista": _Line.GOLD_COAST,  # Fairfield
    "place_fersta": _Line.FERNY_GROVE,  # Ferny Grove
    "place_forsta": _Line.INNER_CITY,  # Fortitude Valley
    "place_frusta": _Line.GOLD_COAST,  # Fruitgrove
    "place_gaista": _Line.ROSEWOOD,  # Gailes
    "place_gaysta": _Line.FERNY_GROVE,  # Gaythorne
    "place_geesta": _Line.NORTH_COAST | _Line.KIPPA_RING,  # Geebung
    "place_gmtsta": _Line.NORTH_COAST,  # Glass House Mountains
    "place_goosta": _Line.ROSEWOOD,  # Goodna
    "place_grasta": _Line.ROSEWOOD | _Line.SPRINGFIELD,  # Graceville
    "place_grosta": _Line.FERNY_GROVE,  # Grovely
    "place_gymsta": _Line.NORTH_COAST,  # Gympie North
    "place_helsta": _Line.GOLD_COAST,  # Helensvale
    "place_hemsta": _Line.CLEVELAND,  # Hemmant
    "place_hensta": _Line.DOOMBEN,  # Hendra
    "place_holsta": _Line.GOLD_COAST,  # Holmview
    "place_indsta": _Line.ROSEWOOD | _Line.SPRINGFIELD,  # Indooroopilly
    "place_intsta": _Line.AIRPORT,  # International Airport
    "place_ipssta": _Line.ROSEWOOD,  # Ipswich
    "place_kalsta": _Line.KIPPA_RING,  # Kallangur
    "place_karsta": _Line.ROSEWOOD,  # Karrabin
    "place_kepsta": _Line.FERNY_GROVE,  # Keperra
    "place_kgtsta": _Line.GOLD_COAST,  # Kingston
    "place_kprsta": _Line.KIPPA_RING,  # Kippa-Ring
    "place_kursta": _Line.GOLD_COAST,  # Kuraby
    "place_lansta": _Line.NORTH_COAST,  # Landsborough
    "place_lawsta": _Line.NORTH_COAST | _Line.KIPPA_RING,  # Lawnton
    "place_linsta": _Line.CLEVELAND,  # Lindum
    "place_logsta": _Line.GOLD_COAST,  # Loganlea
    "place_lotsta": _Line.CLEVELAND,  # Lota
    "place_mhesta": _Line.KIPPA_RING,  # Mango Hill East
    "place_mahsta": _Line.KIPPA_RING,  # Mango Hill
    "place_mansta": _Line.CLEVELAND,  # Manly
    "place_milsta": _Line.ROSEWOOD | _Line.SPRINGFIELD,  # Milton
    "place_mitsta": _Line.FERNY_GROVE,  # Mitchelton
    "place_molsta": _Line.NORTH_COAST,  # Mooloolah
    "place_moosta": _Line.GOLD_COAST,  # Moorooka
    "place_myesta": _Line.NORTH_COAST,  # Morayfield
    "place_mgssta": _Line.CLEVELAND,  # Morningside
    "place_mursta": _Line.NORTH_COAST,  # Murarrie
    "place_mudsta": _Line.KIPPA_RING,  # Murrumba Downs
    "place_namsta": _Line.NORTH_COAST,  # Nambour
    "place_narsta": _Line.NORTH_COAST,  # Narangba
    "place_nrgsta": _Line.GOLD_COAST,  # Nerang
    "place_newsta": _Line.FERNY_GROVE,  # Newmarket
    "place_npksta": _Line.CLEVELAND,  # Norman Park
    "place_nobsta": _Line.SHORNCLIFFE,  # North Boondall
    "place_norsta": _Line.NORTH_COAST | _Line.KIPPA_RING | _Line.SHORNCLIFFE,  # Northgate
    "place_nudsta": _Line.SHORNCLIFFE,  # Nudgee
    "place_nunsta": _Line.NORTH_COAST | _Line.KIPPA_RING | _Line.SHORNCLIFFE,  # Nundah
    "place_omesta": _Line.GOLD_COAST,  # Ormeau
    "place_ormsta": _Line.CLEVELAND,  # Ormiston
    "place_oxfsta": _Line.FERNY_GROVE,  # Oxford Park
    "place_oxlsta": _Line.ROSEWOOD | _Line.SPRINGFIELD,  # Oxley
    "place_palsta": _Line.NORTH_COAST,  # Palmwoods
    "place_petsta": _Line.NORTH_COAST | _Line.KIPPA_RING,  # Petrie
    "place_pomsta": _Line.NORTH_COAST,  # Pomona
    "place_redsta": _Line.ROSEWOOD,  # Redbank
    "place_ricsta": _Line.SPRINGFIELD,  # Richlands
    "place_rivsta": _Line.ROSEWOOD,  # Riverview
    "place_rbnsta": _Line.GOLD_COAST,  # Robina
    "place_rocsta": _Line.GOLD_COAST,  # Rocklea
    "place_romsta": _Line.INNER_CITY,  # Roma Street
    "place_rossta": _Line.ROSEWOOD,  # Rosewood
    "place_rotsta": _Line.KIPPA_RING,  # Rothwell
    "place_runsta": _Line.GOLD_COAST,  # Runcorn
    "place_sgtsta": _Line.SHORNCLIFFE,  # Sandgate
    "place_shesta": _Line.ROSEWOOD | _Line.SPRINGFIELD,  # Sherwood
    "place_shnsta": _Line.SHORNCLIFFE,  # Shorncliffe
    "place_sbasta": _Line.CLEVELAND | _Line.GOLD_COAST,  # South Bank
    "place_sousta": _Line.CLEVELAND | _Line.GOLD_COAST,  # South Brisbane
    "place_spcsta": _Line.SPRINGFIELD,  # Springfield Central
    "place_sprsta": _Line.SPRINGFIELD,  # Springfield
    "place_strsta": _Line.NORTH_COAST | _Line.KIPPA_RING,  # Strathpine
    "place_sunsta": _Line.GOLD_COAST,  # Sunnybank
    "place_snssta": _Line.NORTH_COAST | _Line.KIPPA_RING,  # Sunshine
    "place_tarsta": _Line.ROSEWOOD | _Line.SPRINGFIELD,  # Taringa
    "place_thasta": _Line.ROSEWOOD,  # Thagoona
    "place_thmsta": _Line.ROSEWOOD,  # Thomas Street
    "place_thosta": _Line.CLEVELAND,  # Thorneside
    "place_tomsta": _Line.NORTH_COAST | _Line.KIPPA_RING | _Line.SHORNCLIFFE,  # Toombul
    "place_twgsta": _Line.ROSEWOOD | _Line.SPRINGFIELD,  # Toowong
    "place_trvsta": _Line.NORTH_COAST,  # Traveston
    "place_trista": _Line.GOLD_COAST,  # Trinder Park
    "place_varsta": _Line.GOLD_COAST,  # Varsity Lakes
    "place_virsta": _Line.ROSEWOOD | _Line.SPRINGFIELD,  # Virginia
    "place_wacsta": _Line.ROSEWOOD,  # Wacol
    "place_walsta": _Line.ROSEWOOD,  # Walloon
    "place_welsta": _Line.CLEVELAND,  # Wellington Point
    "place_wilsta": _Line.FERNY_GROVE,  # Wilston
    "place_winsta": _Line.FERNY_GROVE,  # Windsor
    "place_wdrsta": _Line.GOLD_COAST,  # Woodridge
    "place_wolsta": _Line.NORTH_COAST | _Line.KIPPA_RING | _Line.SHORNCLIFFE | _Line.AIRPORT | _Line.DOOMBEN,  # Wooloowin
    "place_wbysta": _Line.NORTH_COAST,  # Woombye
    "place_wulsta": _Line.ROSEWOOD,  # Wulkuraka
    "place_wynsta": _Line.CLEVELAND,  # Wynnum Central
    "place_wyhsta": _Line.CLEVELAND,  # Wynnum North
    "place_wnmsta": _Line.CLEVELAND,  # Wynnum
    "place_yansta": _Line.NORTH_COAST,  # Yandina
    "place_yeesta": _Line.GOLD_COAST,  # Yeerongpilly
    "place_yersta": _Line.GOLD_COAST,  # Yeronga
    "place_zllsta": _Line.NORTH_COAST | _Line.KIPPA_RING,
    # Zillmere
    # fmt: on
}


NO_TRAINS_TEXT = [
    ZWSP,
    "THERE ARE NO {direction} TRAINS",
    "DEPARTING FROM THIS STATION",
    "IN THE NEXT {lookahead} HOURS",
    ZWSP,
    ZWSP,
]


DESTINATION_PREPEND_TEXT = {
    "place_namsta": "Caboolture/",
    "place_rossta": "Ipswich/",
}


NO_TRAINS_SLIM_TEXT = ["THERE ARE NO {direction} TRAINS DEPARTING", "FROM THIS STATION IN THE NEXT {lookahead} HOURS", ZWSP]


def _render_train_bar(stop: Stop, now: datetime.datetime, service: StopTimeInstance) -> str:
    """Renders a train bar.

    Parameters
    ----------
    stop: Stop
        The stop to render the bar for.
    now : datetime.datetime
        The current time.
    service : StopTimeInstance
        The service to render.

    Returns
    -------
    str
        The rendered bar.
    """
    scheduled_time = service.scheduled_departure_time.strftime("%H:%M")

    last_stop = service.trip.stop_times[-1].stop
    while last_stop.parent_station is not None:
        last_stop = last_stop.parent_station
    destination = last_stop.name.split(" station", 1)[0]

    if last_stop.id in DESTINATION_PREPEND_TEXT:
        destination = DESTINATION_PREPEND_TEXT[last_stop.id] + destination

    if LINES[stop.id.lower()] is not _Line.INNER_CITY:
        for stop_time_instance in service.trip.stop_times:
            if stop_time_instance.sequence > service.sequence:
                if LINES[stop_time_instance.stop.id.lower()] is _Line.INNER_CITY:
                    destination = "City & " + destination
                    break

    departs_minutes = (service.actual_departure_time - now).seconds // 60
    if departs_minutes < 60:
        departs = f"{departs_minutes} min"
    else:
        departs = service.actual_departure_time.strftime("%H:%M")

    return (
        _with_formatting(
            f"{scheduled_time:<7}{destination:<{SCREEN_WIDTH - 20}}{service.stop.platform_code:<7}{departs:>6}",
            DiscordAnsiColour.from_route(service.trip.route),
        )
        + "\n"
    )


def _render_train_bars(stop: Stop, now: datetime.datetime, services: Sequence[StopTimeInstance], max_bars: int) -> str:
    text = ""

    for service in services[:max_bars]:
        text += _render_train_bar(stop, now, service)
    for _ in range(max_bars - len(services)):
        text += ZWSP + "\n"

    return text


def _render_no_trains_text(direction: str, lookahead_hours: int, slim: bool = False) -> str:
    """Renders the no trains text.

    Parameters
    ----------
    direction : Direction
        The direction of the route.
    lookahead_hours : int
        The number of hours ahead services are being displayed for.
    slim : bool, optional
        Whether to render the slim version of the text.

    Returns
    -------
    str
        The rendered text.
    """
    if slim:
        text = NO_TRAINS_SLIM_TEXT
    else:
        text = NO_TRAINS_TEXT

    return "\n".join(
        _with_formatting(f"{line.format(direction=direction, lookahead=lookahead_hours):^{SCREEN_WIDTH}}", DiscordAnsiColour.WHITE)
        for line in text
    )


def _render_train_timetable(
    stop: Stop,
    now: datetime.datetime,
    upward_services: Sequence[StopTimeInstance],
    downward_services: Sequence[StopTimeInstance],
    lookahead_hours: int,
    direction: Direction | None,
) -> str:
    """Renders a train timetable for a stop.

    Parameters
    ----------
    stop : Stop
        The stop to render the timetable for.
    now : datetime.datetime
        The current time.
    upward_services : Sequence[StopTimeInstance]
        The upward services to render.
    downward_services : Sequence[StopTimeInstance]
        The downward services to render.
    lookahead_hours : int
        The number of hours ahead services are being displayed for.
    direction : Direction
        The direction of the route.

    Returns
    -------
    str
        The rendered timetable.
    """
    inbound_direction = _get_inbound_direction(stop.id)
    outbound_direction = Direction.DOWNWARD if inbound_direction is Direction.UPWARD else Direction.UPWARD

    line = LINES[stop.id.lower()]
    if line is _Line.INNER_CITY:
        up_text = "SOUTHBOUND"
        down_text = "NORTHBOUND"
    else:
        up_text = "INBOUND" if inbound_direction is Direction.UPWARD else "OUTBOUND"
        down_text = "OUTBOUND" if inbound_direction is Direction.UPWARD else "INBOUND"

    if direction is not None:
        text = (
            _with_formatting(f"[{now.strftime("%I:%M:%S")}]", DiscordAnsiColour.YELLOW, bold=True)
            + _with_formatting(f"{f"Next Trains {_get_header_text(stop.id)[direction]}":^{SCREEN_WIDTH - 10}}", DiscordAnsiColour.WHITE)
            + "\n"
        )

        services = upward_services if direction is Direction.UPWARD else downward_services

        if services:
            text += "Service                        Platform  Departs\n"
            text += _render_train_bars(stop, now, services, MAX_NEXT_TRAINS)

        else:
            text += _render_no_trains_text(up_text if direction is Direction.UPWARD else down_text, lookahead_hours) + "\n"

    else:
        if LINES[stop.id.lower()] is _Line.INNER_CITY:
            text = (
                _with_formatting(f"[{now.strftime("%I:%M:%S")}]", DiscordAnsiColour.YELLOW, bold=True)
                + _with_formatting(f"{f"Next 3 Trains North and South/West":^{SCREEN_WIDTH - 10}}", DiscordAnsiColour.WHITE)
                + "\n"
            )
        else:
            text = (
                _with_formatting(f"[{now.strftime("%I:%M:%S")}]", DiscordAnsiColour.YELLOW, bold=True)
                + _with_formatting(f"{f"Next 3 Inbound and Outbound Trains":^{SCREEN_WIDTH - 10}}", DiscordAnsiColour.WHITE)
                + "\n"
            )

        text += f"{f"Next Trains {_get_header_text(stop.id, slim=True)[inbound_direction]:<{SCREEN_WIDTH - 29}}"}Platform  Departs\n"
        inbound_services = upward_services if inbound_direction is Direction.UPWARD else downward_services
        if inbound_services:
            text += _render_train_bars(stop, now, inbound_services, MAX_NEXT_TRAINS // 2)
        else:
            text += (
                _render_no_trains_text(up_text if inbound_direction is Direction.UPWARD else down_text, lookahead_hours, slim=True) + "\n"
            )

        text += f"{f"Next Trains {_get_header_text(stop.id, slim=True)[outbound_direction]:<{SCREEN_WIDTH - 29}}"}Platform  Departs\n"
        outbound_services = upward_services if outbound_direction is Direction.UPWARD else downward_services
        if outbound_services:
            text += _render_train_bars(stop, now, outbound_services, MAX_NEXT_TRAINS // 2)
        else:
            text += (
                _render_no_trains_text(up_text if outbound_direction is Direction.UPWARD else down_text, lookahead_hours, slim=True) + "\n"
            )

    return text


NO_SERVICES_TEXT = """\

             THERE ARE NO SERVICES
              DEPARTING THIS STOP
              IN THE NEXT {} HOURS


"""


def _render_bus_timetable(
    stop: Stop,
    now: datetime.datetime,
    services: Sequence[StopTimeInstance],
    lookahead_hours: int,
) -> str:
    """Renders a bus timetable for a stop.

    Parameters
    ----------
    stop : Stop
        The stop to render the timetable for.
    now : datetime.datetime
        The current time.
    stop_times : Sequence[StopTimeInstance]
        The stop times to render.
    lookahead_hours : int
        The number of hours ahead services are being displayed for.

    Returns
    -------
    str
        The rendered timetable.
    """
    text = _with_formatting("Route  Destination                       Departs", DiscordAnsiColour.WHITE, bold=True) + "\n"
    for service in services:
        departs_minutes = (service.actual_departure_time - now).seconds // 60
        if departs_minutes < 60:
            departs = f"{departs_minutes} min"
        else:
            departs = service.actual_departure_time.strftime("%H:%M")
        text += (
            _with_formatting(
                f"{service.trip.route.short_name:<7}{service.trip.headsign:<{SCREEN_WIDTH-13}}{departs:>6}",
                DiscordAnsiColour.from_route(service.trip.route),
            )
            + "\n"
        )

    if not services:
        text += _with_formatting(NO_SERVICES_TEXT.format(lookahead_hours), DiscordAnsiColour.WHITE)

    return text


TRAM_FOOTERS = [
    """\
                For your safety
        CCTV is in operation at all times\
""",
    """\
                  NO SMOKING
                                      No smoking\
""",
]


def _render_tram_timetable(now: datetime.datetime, stop_times: Sequence[StopTimeInstance]) -> str:
    """Renders a tram timetable for a stop.

    Parameters
    ----------
    now : datetime.datetime
        The current time.
    stop_times : Sequence[StopTimeInstance]
        The stop times to render.

    Returns
    -------
    str
        The rendered timetable.
    """
    text = ""

    for i in range(2):
        if i < len(stop_times):
            stop_time = stop_times[i]

            destination = stop_time.trip.headsign

            departs_minutes = (stop_time.actual_departure_time - now).seconds // 60
            if departs_minutes < 60:
                departs = f"{departs_minutes} min"
            else:
                departs = stop_time.actual_departure_time.strftime("%H:%M")

            text += _with_formatting(
                f"Plat{stop_time.stop.platform_code:<3}{destination:<{SCREEN_WIDTH-14}}{departs:>6}\n", DiscordAnsiColour.YELLOW
            )
        else:
            text += f"{ZWSP}\n"

    text += _with_formatting(f"{now.strftime("%I:%M:%S %p").lower():^{SCREEN_WIDTH}}\n", DiscordAnsiColour.WHITE, bold=True)
    text += choice(TRAM_FOOTERS)

    return text


def _render_ferry_timetable(
    stop: Stop,
    now: datetime.datetime,
    services: Sequence[StopTimeInstance],
    lookahead_hours: int,
) -> str:
    """Renders a ferry timetable for a stop.

    Parameters
    ----------
    stop : Stop
        The stop to render the timetable for.
    now : datetime.datetime
        The current time.
    stop_times : Sequence[StopTimeInstance]
        The stop times to render.
    lookahead_hours : int
        The number of hours ahead services are being displayed for.

    Returns
    -------
    str
        The rendered timetable.
    """
    return _render_bus_timetable(stop, now, services, lookahead_hours)


@overload
def render_timetable(
    stop: Stop,
    now: datetime.datetime,
    services: Sequence[StopTimeInstance],
    type: Literal[RouteType.RAIL],
    lookahead_hours: int,
    direction: Direction | None = ...,
) -> str: ...


@overload
def render_timetable(
    stop: Stop,
    now: datetime.datetime,
    services: Sequence[StopTimeInstance],
    type: RouteType,
    lookahead_hours: int,
) -> str: ...


def render_timetable(
    stop: Stop,
    now: datetime.datetime,
    services: Sequence[StopTimeInstance],
    type: RouteType,
    lookahead_hours: int,
    direction: Direction | None = None,
) -> str:
    """Render a timetable for a stop.

    Parameters
    ----------
    stop : Stop
        The stop to render the timetable for.
    now : datetime.datetime
        The current time.
    services : Sequence[StopTimeInstance]
        The services to render.
    type : RouteType
        The type of route.
    lookahead_hours : int
        The number of hours ahead services are being displayed for.
    direction : Direction, optional
        The direction of the route, this only applies to trains.

    Returns
    -------
    str
        The rendered timetable.
    """
    if type is RouteType.RAIL:
        if direction is None and stop.id.lower() in END_OF_LINE:
            direction = _get_inbound_direction(stop.id)

        upward_services = [service for service in services if service.trip.direction is Direction.UPWARD]
        downward_services = [service for service in services if service.trip.direction is Direction.DOWNWARD]
        return _render_train_timetable(stop, now, upward_services, downward_services, lookahead_hours, direction)
    elif type is RouteType.BUS:
        return _render_bus_timetable(stop, now, services, lookahead_hours)
    elif type is RouteType.TRAM:
        return _render_tram_timetable(now, services)
    elif type is RouteType.FERRY:
        return _render_ferry_timetable(stop, now, services, lookahead_hours)
    else:
        raise ValueError(f"Unsupported route type: {type}")
