"""
Geometry module for Smart Signal — handles geometric calculations.
"""
import math
from typing import Tuple, List
import cv2
import numpy as np


def point_in_polygon(
    pt: Tuple[float, float],
    polygon_pts: List[Tuple[float, float]],
) -> bool:
    """cv2.pointPolygonTest wrapper. Returns True if pt is inside."""
    if len(polygon_pts) < 3:
        return False
    contour = np.array(polygon_pts, dtype=np.float32)
    return cv2.pointPolygonTest(contour, (float(pt[0]), float(pt[1])), False) >= 0


def point_to_segment_distance(
    pt: Tuple[float, float],
    seg_a: Tuple[float, float],
    seg_b: Tuple[float, float],
) -> float:
    """Shortest distance from a point to a line segment."""
    ax, ay = seg_a
    bx, by = seg_b
    px, py = pt
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    proj_x, proj_y = ax + t * dx, ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def crossed_line(
    prev: Tuple[float, float],
    curr: Tuple[float, float],
    line_a: Tuple[float, float],
    line_b: Tuple[float, float],
) -> bool:
    """Check if the segment prev→curr crosses the line segment a→b."""
    def ccw(a, b, c):
        return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])
    return ccw(line_a, line_b, prev) != ccw(line_a, line_b, curr) and \
           ccw(prev, curr, line_a) != ccw(prev, curr, line_b)