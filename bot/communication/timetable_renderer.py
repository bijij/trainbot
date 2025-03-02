import datetime
from collections.abc import Mapping, Sequence
from enum import Flag, auto
from zoneinfo import ZoneInfo

from ..model.gtfs import Colour, Direction, RouteType, Stop, StopTimeInstance

ANSI_ESCAPE = "\033[0;"
ANSI_RESET = f"{ANSI_ESCAPE}0m"

ANSI_FORMATING = {...}

COLOUR_CODES = {
    Colour.RED: "31",
    Colour.GREEN: "32",
    Colour.GOLD: "33",
    Colour.BLUE: "34",
    Colour.PURPLE: "35",
    Colour.CYAN: "36",
    Colour.WHITE: "37",
    Colour.GREY: "30",
}


BRISBANE = ZoneInfo("Australia/Brisbane")


SCREEN_WIDTH = 48


def with_colour(colour: Colour, text: str, bold: bool = False, underline: bool = False) -> str:
    code = COLOUR_CODES[colour]
    if bold:
        code += ";1"
    if underline:
        code += ";4"

    return f"{ANSI_ESCAPE}{code}m{text}{ANSI_RESET}"


class Line(Flag):
    NORTH_COAST = auto()
    KIPPA_RING = auto()
    SHORNCLIFFE = auto()
    AIRPORT = auto()
    DOOMBEN = auto()
    FERNY_GROVE = auto()
    INNER_CITY = auto()
    CLEVELAND = auto()
    GOLD_COAST = auto()
    SPRINGFIELD = auto()
    ROSEWOOD = auto()


NORTHSIDE = Line.NORTH_COAST | Line.KIPPA_RING | Line.SHORNCLIFFE | Line.AIRPORT | Line.DOOMBEN | Line.FERNY_GROVE
SOUTHSIDE = Line.CLEVELAND | Line.GOLD_COAST | Line.SPRINGFIELD | Line.ROSEWOOD


OUTBOUND_DIRECTIONS = {
    Line.NORTH_COAST: {
        "North",
    },
    Line.KIPPA_RING: {
        "North",
    },
    Line.SHORNCLIFFE: {
        "North",
    },
    Line.AIRPORT: {
        "North",
    },
    Line.DOOMBEN: {
        "East",
    },
    Line.FERNY_GROVE: {
        "North",
    },
    Line.CLEVELAND: {"South", "East"},
    Line.GOLD_COAST: {
        "South",
    },
    Line.SPRINGFIELD: {
        "South",
    },
    Line.ROSEWOOD: {
        "West",
    },
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


def get_header_text(line: Line) -> Mapping[Direction, str]:
    if line is Line.INNER_CITY:
        return {Direction.UPWARD: "Trains (1-6) South/West", Direction.DOWNWARD: "Trains (1-6) North"}

    outbound_directions = set()
    for line_ in Line:
        if line & line_:
            outbound_directions |= OUTBOUND_DIRECTIONS[line_]

    if line & NORTHSIDE:
        upward_text = "City & South/West"
        downward_text = "/".join(outbound_directions)
    else:
        downward_text = "City & North"
        upward_text = "/".join(outbound_directions)

    outbound_directions = set()

    return {Direction.DOWNWARD: downward_text, Direction.UPWARD: upward_text}


HEADER_TEXT = {
    stop_id: get_header_text(lines)
    for stop_id, lines in {
        "place_albsta": Line.NORTH_COAST | Line.KIPPA_RING | Line.SHORNCLIFFE | Line.AIRPORT | Line.DOOMBEN,  # Albion
        "place_aldsta": Line.FERNY_GROVE,  # Alderley
        "place_altsta": Line.GOLD_COAST,  # Altandi
        "place_ascsta": Line.DOOMBEN,  # Ascot
        "place_aucsta": Line.ROSEWOOD | Line.SPRINGFIELD,  # Auchenflower
        "place_balsta": Line.NORTH_COAST | Line.KIPPA_RING,  # Bald Hills
        "place_bansta": Line.GOLD_COAST,  # Banoon
        "place_beesta": Line.GOLD_COAST,  # Beenleigh
        "place_bbrsta": Line.NORTH_COAST,  # Beerburrum
        "place_bwrsta": Line.NORTH_COAST,  # Beerwah
        "place_betsta": Line.GOLD_COAST,  # Bethania
        "place_binsta": Line.SHORNCLIFFE,  # Bindha
        "place_birsta": Line.CLEVELAND,  # Birkdale
        "place_parsta": Line.CLEVELAND | Line.GOLD_COAST,  # Boggo Road/Park Road
        "place_bdlsta": Line.SHORNCLIFFE,  # Boondall
        "place_bvlsta": Line.ROSEWOOD,  # Booval
        "place_bowsta": Line.NORTH_COAST
        | Line.KIPPA_RING
        | Line.SHORNCLIFFE
        | Line.AIRPORT
        | Line.DOOMBEN
        | Line.FERNY_GROVE,  # Bowen Hills
        "place_brasta": Line.NORTH_COAST | Line.KIPPA_RING,  # Bray Park
        "place_bunsta": Line.ROSEWOOD,  # Bundamba
        "place_bursta": Line.NORTH_COAST,  # Burpengary
        "place_cabstn": Line.NORTH_COAST,  # Caboolture
        "place_cansta": Line.CLEVELAND,  # Cannon Hill
        "place_cassta": Line.NORTH_COAST | Line.KIPPA_RING,  # Carseldine
        "place_censta": Line.INNER_CITY,  # Central
        "place_chesta": Line.ROSEWOOD | Line.SPRINGFIELD,  # Chelmer
        "place_clasta": Line.DOOMBEN,  # Clayfield
        "place_clesta": Line.CLEVELAND,  # Cleveland
        "place_cmrstn": Line.GOLD_COAST,  # Coomera
        "place_cppsta": Line.GOLD_COAST,  # Coopers Plains
        "place_crnsta": Line.NORTH_COAST,  # Cooran
        "place_crysta": Line.NORTH_COAST,  # Cooroy
        "place_coosta": Line.CLEVELAND,  # Coorparoo
        "place_corsta": Line.ROSEWOOD | Line.SPRINGFIELD,  # Corinda
        "place_daksta": Line.NORTH_COAST,  # Dakabin
        "place_darsta": Line.ROSEWOOD | Line.SPRINGFIELD,  # Darra
        "place_deasta": Line.SPRINGFIELD,  # Deagon
        "place_dinsta": Line.ROSEWOOD,  # Dinmore
        "place_domsta": Line.AIRPORT,  # Domestic Airport
        "place_dbnsta": Line.DOOMBEN,  # Doomben
        "place_dupsta": Line.GOLD_COAST,  # Dutton Park
        "place_egjsta": Line.NORTH_COAST | Line.KIPPA_RING | Line.SHORNCLIFFE | Line.AIRPORT | Line.DOOMBEN,  # Eagle Junction
        "place_eassta": Line.ROSEWOOD,  # East Ipswich
        "place_ebbsta": Line.ROSEWOOD,  # Ebbw Vale
        "place_edesta": Line.GOLD_COAST,  # Edens Landing
        "place_elmsta": Line.NORTH_COAST,  # Elimbah
        "place_enosta": Line.FERNY_GROVE,  # Enoggera
        "place_eudsta": Line.NORTH_COAST,  # Eudlo
        "place_eumsta": Line.NORTH_COAST,  # Eumundi
        "place_faista": Line.GOLD_COAST,  # Fairfield
        "place_fersta": Line.FERNY_GROVE,  # Ferny Grove
        "place_forsta": Line.INNER_CITY,  # Fortitude Valley
        "place_frusta": Line.GOLD_COAST,  # Fruitgrove
        "place_gaista": Line.ROSEWOOD,  # Gailes
        "place_gaysta": Line.FERNY_GROVE,  # Gaythorne
        "place_geesta": Line.NORTH_COAST | Line.KIPPA_RING,  # Geebung
        "place_gmtsta": Line.NORTH_COAST,  # Glass House Mountains
        "place_goosta": Line.ROSEWOOD,  # Goodna
        "place_grasta": Line.ROSEWOOD | Line.SPRINGFIELD,  # Graceville
        "place_grosta": Line.FERNY_GROVE,  # Grovely
        "place_gymsta": Line.NORTH_COAST,  # Gympie North
        "place_helsta": Line.GOLD_COAST,  # Helensvale
        "place_hemsta": Line.CLEVELAND,  # Hemmant
        "place_hensta": Line.DOOMBEN,  # Hendra
        "place_holsta": Line.GOLD_COAST,  # Holmview
        "place_indsta": Line.ROSEWOOD | Line.SPRINGFIELD,  # Indooroopilly
        "place_intsta": Line.AIRPORT,  # International Airport
        "place_ipssta": Line.ROSEWOOD,  # Ipswich
        "place_kalsta": Line.KIPPA_RING,  # Kallangur
        "place_karsta": Line.ROSEWOOD,  # Karrabin
        "place_kepsta": Line.FERNY_GROVE,  # Keperra
        "place_kgtsta": Line.GOLD_COAST,  # Kingston
        "place_kprsta": Line.KIPPA_RING,  # Kippa-Ring
        "place_kursta": Line.GOLD_COAST,  # Kuraby
        "place_lansta": Line.NORTH_COAST,  # Landsborough
        "place_lawsta": Line.NORTH_COAST | Line.KIPPA_RING,  # Lawnton
        "place_linsta": Line.CLEVELAND,  # Lindum
        "place_logsta": Line.GOLD_COAST,  # Loganlea
        "place_lotsta": Line.CLEVELAND,  # Lota
        "place_mhesta": Line.KIPPA_RING,  # Mango Hill East
        "place_mahsta": Line.KIPPA_RING,  # Mango Hill
        "place_mansta": Line.CLEVELAND,  # Manly
        "place_milsta": Line.ROSEWOOD | Line.SPRINGFIELD,  # Milton
        "place_mitsta": Line.FERNY_GROVE,  # Mitchelton
        "place_molsta": Line.NORTH_COAST,  # Mooloolah
        "place_moosta": Line.GOLD_COAST,  # Moorooka
        "place_myesta": Line.NORTH_COAST,  # Morayfield
        "place_mgssta": Line.CLEVELAND,  # Morningside
        "place_mursta": Line.NORTH_COAST,  # Murarrie
        "place_mudsta": Line.KIPPA_RING,  # Murrumba Downs
        "place_namsta": Line.NORTH_COAST,  # Nambour
        "place_narsta": Line.NORTH_COAST,  # Narangba
        "place_nrgsta": Line.GOLD_COAST,  # Nerang
        "place_newsta": Line.FERNY_GROVE,  # Newmarket
        "place_npksta": Line.CLEVELAND,  # Norman Park
        "place_nobsta": Line.SHORNCLIFFE,  # North Boondall
        "place_norsta": Line.NORTH_COAST | Line.KIPPA_RING | Line.SHORNCLIFFE,  # Northgate
        "place_nudsta": Line.SHORNCLIFFE,  # Nudgee
        "place_nunsta": Line.NORTH_COAST | Line.KIPPA_RING | Line.SHORNCLIFFE,  # Nundah
        "place_omesta": Line.GOLD_COAST,  # Ormeau
        "place_ormsta": Line.CLEVELAND,  # Ormiston
        "place_oxfsta": Line.FERNY_GROVE,  # Oxford Park
        "place_oxlsta": Line.ROSEWOOD | Line.SPRINGFIELD,  # Oxley
        "place_palsta": Line.NORTH_COAST,  # Palmwoods
        "place_petsta": Line.NORTH_COAST | Line.KIPPA_RING,  # Petrie
        "place_pomsta": Line.NORTH_COAST,  # Pomona
        "place_redsta": Line.ROSEWOOD,  # Redbank
        "place_ricsta": Line.SPRINGFIELD,  # Richlands
        "place_rivsta": Line.ROSEWOOD,  # Riverview
        "place_rbnsta": Line.GOLD_COAST,  # Robina
        "place_rocsta": Line.GOLD_COAST,  # Rocklea
        "place_romsta": Line.INNER_CITY,  # Roma Street
        "place_rossta": Line.ROSEWOOD,  # Rosewood
        "place_rotsta": Line.KIPPA_RING,  # Rothwell
        "place_runsta": Line.GOLD_COAST,  # Runcorn
        "place_sgtsta": Line.SHORNCLIFFE,  # Sandgate
        "place_shesta": Line.ROSEWOOD | Line.SPRINGFIELD,  # Sherwood
        "place_shnsta": Line.SHORNCLIFFE,  # Shorncliffe
        "place_sbasta": Line.CLEVELAND | Line.GOLD_COAST,  # South Bank
        "place_sousta": Line.CLEVELAND | Line.GOLD_COAST,  # South Brisbane
        "place_spcsta": Line.SPRINGFIELD,  # Springfield Central
        "place_sprsta": Line.SPRINGFIELD,  # Springfield
        "place_strsta": Line.NORTH_COAST | Line.KIPPA_RING,  # Strathpine
        "place_sunsta": Line.GOLD_COAST,  # Sunnybank
        "place_snssta": Line.NORTH_COAST | Line.KIPPA_RING,  # Sunshine
        "place_tarsta": Line.ROSEWOOD | Line.SPRINGFIELD,  # Taringa
        "place_thasta": Line.ROSEWOOD,  # Thagoona
        "place_thmsta": Line.ROSEWOOD,  # Thomas Street
        "place_thosta": Line.CLEVELAND,  # Thorneside
        "place_tomsta": Line.NORTH_COAST | Line.KIPPA_RING | Line.SHORNCLIFFE,  # Toombul
        "place_twgsta": Line.ROSEWOOD | Line.SPRINGFIELD,  # Toowong
        "place_trvsta": Line.NORTH_COAST,  # Traveston
        "place_trista": Line.GOLD_COAST,  # Trinder Park
        "place_varsta": Line.GOLD_COAST,  # Varsity Lakes
        "place_virsta": Line.ROSEWOOD | Line.SPRINGFIELD,  # Virginia
        "place_wacsta": Line.ROSEWOOD,  # Wacol
        "place_walsta": Line.ROSEWOOD,  # Walloon
        "place_welsta": Line.CLEVELAND,  # Wellington Point
        "place_wilsta": Line.FERNY_GROVE,  # Wilston
        "place_winsta": Line.FERNY_GROVE,  # Windsor
        "place_wdrsta": Line.GOLD_COAST,  # Woodridge
        "place_wolsta": Line.NORTH_COAST | Line.KIPPA_RING | Line.SHORNCLIFFE | Line.AIRPORT | Line.DOOMBEN,  # Wooloowin
        "place_wbysta": Line.NORTH_COAST,  # Woombye
        "place_wulsta": Line.ROSEWOOD,  # Wulkuraka
        "place_wynsta": Line.CLEVELAND,  # Wynnum Central
        "place_wyhsta": Line.CLEVELAND,  # Wynnum North
        "place_wnmsta": Line.CLEVELAND,  # Wynnum
        "place_yansta": Line.NORTH_COAST,  # Yandina
        "place_yeesta": Line.GOLD_COAST,  # Yeerongpilly
        "place_yersta": Line.GOLD_COAST,  # Yeronga
        "place_zllsta": Line.NORTH_COAST | Line.KIPPA_RING,  # Zillmere
    }.items()
}


NO_TRAINS_TEXT = """\

               THERE ARE NO TRAINS              
              DEPARTING THIS STATION            
               IN THE NEXT 4 HOURS              

"""


def render_train_timetable(
    stop: Stop,
    now: datetime.datetime,
    services: Sequence[StopTimeInstance],
    direction: Direction,
) -> str:
    text = (
        with_colour(Colour.GOLD, f"[{now.strftime("%I:%M:%S")}]", bold=True)
        + with_colour(Colour.WHITE, f"{f"Next Trains {HEADER_TEXT[stop.id][direction]}":^38}")
        + "\n"
    )

    if services:

        text += "Service                      Platform    Departs\n"

        for service in services:
            scheduled_time = service.scheduled_departure_time.strftime("%H:%M")

            destination = service.trip.stop_times[-1].stop.name.split(" station,", 1)[0]

            departs_minutes = (service.scheduled_departure_time - now).seconds // 60
            if departs_minutes < 60:
                departs = f"{departs_minutes} min"
            else:
                departs = service.scheduled_departure_time.strftime("%H:%M")

            text += (
                with_colour(
                    service.trip.route.colour,
                    f"{scheduled_time:<7}{destination:<26}{service.stop.platform_code:<9}{departs:>6}",
                )
                + "\n"
            )

    else:
        text += with_colour(Colour.WHITE, NO_TRAINS_TEXT, bold=True)

    return text


def render_bus_timetable(stop: Stop, now: datetime.datetime, services: Sequence[StopTimeInstance]) -> str:
    text = with_colour(Colour.WHITE, "Route  Destination                       Departs", bold=True) + "\n"
    for service in services:
        departs_minutes = (service.scheduled_departure_time - now).seconds // 60
        departs = f"{departs_minutes} min"
        text += with_colour(service.trip.route.colour, f"{service.trip.route.short_name:<7}{service.trip.headsign:<34}{departs:>6}") + "\n"

    return text


def render_timetable(
    stop: Stop,
    now: datetime.datetime,
    services: Sequence[StopTimeInstance],
    type: RouteType,
    direction: Direction | None = None,
) -> str:
    now = now.astimezone(BRISBANE)

    if type is RouteType.BUS:
        return render_bus_timetable(stop, now, services)
    elif type is RouteType.RAIL:
        assert direction is not None
        return render_train_timetable(stop, now, services, direction)
    else:
        raise ValueError(f"Unsupported route type: {type}")
