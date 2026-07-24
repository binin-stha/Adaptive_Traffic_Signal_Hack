"""Project-wide constants."""

DIRECTIONS = ["north", "south", "east", "west"]

DIR_COLORS = {
    "north": "#3B82F6",
    "south": "#22C55E",
    "east": "#F59E0B",
    "west": "#EC4899",
}

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