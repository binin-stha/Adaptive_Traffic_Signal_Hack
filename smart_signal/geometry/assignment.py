"""Assign detections to drawn shapes and count per-direction traffic."""

import math
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np

from geometry.shapes import point_in_polygon, crossed_line


# ─────────────────────────────────────────────────────────────────────────────
# SHAPE ASSIGNMENT
# ─────────────────────────────────────────────────────────────────────────────

def assign_to_shapes(
    dets: List[Dict[str, Any]],
    shapes: List[Dict[str, Any]],
    track_history: dict | None = None,
) -> List[Dict[str, Any]]:
    """Tag each detection with the lane / crossing / count-line it falls in.

    Mutates each detection dict in-place and returns the list.
    """
    lanes = [s for s in shapes if s["label"] == "lane"]
    crossings = [s for s in shapes if s["label"] == "zebra_crossing"]
    count_lines = [s for s in shapes if s["label"] == "count_line"]

    for d in dets:
        d["lane_id"] = None
        d["in_crossing"] = False
        d["crossed_count_line"] = False

        # Lane assignment (point-in-polygon on center)
        for lane in lanes:
            if point_in_polygon(d["center"], lane["points"]):
                d["lane_id"] = lane["id"]
                break

        # Crossing assignment
        for cx in crossings:
            if point_in_polygon(d["center"], cx["points"]):
                d["in_crossing"] = True
                break

        # Count-line crossing (needs previous position from track history)
        if track_history and d["track_id"] in track_history:
            hist = track_history[d["track_id"]]
            if len(hist) >= 2:
                prev = hist[-2]
                curr = hist[-1]
                for cl in count_lines:
                    if len(cl["points"]) == 2:
                        if crossed_line(prev, curr, cl["points"][0], cl["points"][1]):
                            d["crossed_count_line"] = True
                            break

    return dets


# ─────────────────────────────────────────────────────────────────────────────
# COUNTING
# ─────────────────────────────────────────────────────────────────────────────

def counts_for_direction(
    dets: List[Dict[str, Any]],
    shapes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Count vehicles (incoming + focus lanes only) and pedestrians.

    Returns a dict with all metrics the decision engine needs.
    """
    lanes_by_id = {s["id"]: s for s in shapes if s["label"] == "lane"}

    vehicle_count = 0
    pedestrian_count = 0
    waiting_vehicles = 0
    waiting_pedestrians = 0
    crossing_pedestrians = 0
    count_line_crossings = 0

    for d in dets:
        if d["category"] == "vehicle":
            lane = lanes_by_id.get(d["lane_id"])
            if lane and lane.get("travel") == "incoming" and lane.get("focus", True):
                vehicle_count += 1
                if d["state"] == "waiting":
                    waiting_vehicles += 1
            if d.get("crossed_count_line"):
                count_line_crossings += 1

        elif d["category"] == "pedestrian":
            pedestrian_count += 1
            if d["state"] == "waiting":
                waiting_pedestrians += 1
            if d.get("in_crossing") and d["state"] == "moving":
                crossing_pedestrians += 1

    return {
        "vehicle": vehicle_count,
        "pedestrian": pedestrian_count,
        "waiting_vehicles": waiting_vehicles,
        "waiting_pedestrians": waiting_pedestrians,
        "crossing_pedestrians": crossing_pedestrians,
        "count_line_crossings": count_line_crossings,
    }