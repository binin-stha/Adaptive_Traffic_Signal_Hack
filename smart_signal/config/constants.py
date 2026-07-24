"""Project-wide constants."""

DIRECTIONS = ["north", "south", "east", "west"]

DIR_META = {
    "north": {"label": "NORTH", "arrow": "▲", "color": "#3B82F6", "pos": (0, 1)},
    "west":  {"label": "WEST",  "arrow": "◀", "color": "#EC4899", "pos": (1, 0)},
    "east":  {"label": "EAST",  "arrow": "▶", "color": "#F59E0B", "pos": (1, 2)},
    "south": {"label": "SOUTH", "arrow": "▼", "color": "#22C55E", "pos": (2, 1)},
}

DIR_COLORS = {d: DIR_META[d]["color"] for d in DIRECTIONS}

WEIGHTS = {"vehicle": 1.5, "pedestrian": 1.2}
BASE_TIME = 10
MIN_GREEN = 10
MAX_GREEN = 60
MAX_WAIT = 90
SPEED_THRESH_DEFAULT = 3.0
CANVAS_HEIGHT = 480

SHAPE_COLORS = {
    "lane": (255, 220, 0),
    "zebra_crossing": (255, 0, 220),
    "stop_line": (0, 180, 255),
    "count_line": (0, 255, 255),
}

BBOX_COLORS = {
    "vehicle": (0, 200, 80),
    "pedestrian": (60, 60, 255),
    "pedestrian_crossing": (0, 140, 255),
}