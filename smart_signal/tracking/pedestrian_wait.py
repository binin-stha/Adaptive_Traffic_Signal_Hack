"""Pedestrian wait-time tracking near zebra crossings."""

from typing import Any, Dict, List

from geometry.shapes import point_in_polygon, point_to_segment_distance


class PedestrianWaitTracker:
    """Tracks how long each pedestrian has been waiting near a crossing.

    Classifies each tracked pedestrian as:
        walking / standing / waiting_to_cross / crossing
    and accumulates a per-track wait timer while they wait near the zebra.
    """

    def __init__(self, near_buffer: float = 60.0):
        self.near_buffer = near_buffer
        self.peds: Dict[int, Dict[str, Any]] = {}

    def _near_crossing(self, center, crossings) -> bool:
        for c in crossings:
            pts = c["points"]
            for i in range(len(pts)):
                a = pts[i]
                b = pts[(i + 1) % len(pts)]
                if point_to_segment_distance(center, a, b) < self.near_buffer:
                    return True
        return False

    def update(self, dets, shapes, dt):
        crossings = [s for s in shapes if s["label"] == "zebra_crossing"]
        active = set()

        for d in dets:
            if d["category"] != "pedestrian":
                continue
            tid = d["track_id"]
            active.add(tid)

            p = self.peds.setdefault(tid, {
                "wait_time": 0.0,
                "near_crossing": False,
                "in_crossing": False,
                "state": "walking",
            })

            in_cx = any(point_in_polygon(d["center"], c["points"]) for c in crossings)
            near_cx = in_cx or (bool(crossings) and self._near_crossing(d["center"], crossings))

            p["in_crossing"] = in_cx
            p["near_crossing"] = near_cx

            if in_cx and d["state"] == "moving":
                p["state"] = "crossing"
                p["wait_time"] = 0.0
            elif near_cx and d["state"] == "waiting":
                p["state"] = "waiting_to_cross"
                p["wait_time"] += dt
            elif d["state"] == "waiting":
                p["state"] = "standing"
            else:
                p["state"] = "walking"
                if not near_cx:
                    p["wait_time"] = max(0.0, p["wait_time"] - dt * 2)

            d["ped_wait_time"] = round(p["wait_time"], 1)
            d["ped_state"] = p["state"]

        for tid in list(self.peds.keys()):
            if tid not in active:
                del self.peds[tid]

        return dets