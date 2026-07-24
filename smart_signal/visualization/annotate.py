"""
Visualization module for Smart Signal — handles frame annotation with shapes and detections.
"""
from typing import List, Dict, Any
import cv2
import numpy as np
from config.constants import SHAPE_COLORS, BBOX_COLORS


def annotate_frame(
    frame: np.ndarray,
    dets: List[Dict[str, Any]],
    shapes: List[Dict[str, Any]],
) -> np.ndarray:
    """Draw shapes + detection boxes on a copy of the frame."""
    out = frame.copy()

    # Draw shapes
    for s in shapes:
        pts = np.array(s["points"], dtype=np.int32)
        color = SHAPE_COLORS.get(s["label"], (200, 200, 200))

        if s["label"] == "lane":
            cv2.polylines(out, [pts], True, color, 2)
            tag = s.get("id", "lane")
            focus = " *" if s.get("focus") else ""
            cv2.putText(
                out, f"{tag}{focus}", tuple(pts[0]),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2,
            )
        elif s["label"] == "zebra_crossing":
            cv2.polylines(out, [pts], True, color, 2)
            cv2.putText(
                out, "CROSSING", tuple(pts[0]),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2,
            )
        elif s["label"] in ("stop_line", "count_line"):
            if len(pts) >= 2:
                cv2.line(out, tuple(pts[0]), tuple(pts[1]), color, 3)
                cv2.putText(
                    out, s["label"].upper(), tuple(pts[0]),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 2,
                )

    # Draw detections
    for d in dets:
        x1, y1, x2, y2 = map(int, d["bbox"])
        label = d["category"]
        if label == "pedestrian" and d.get("in_crossing"):
            label = "pedestrian_crossing"
        color = BBOX_COLORS.get(label, (200, 200, 200))
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        text = f"{label} #{d['track_id']} ({d['state']})"
        cv2.putText(
            out, text, (x1, max(y1 - 6, 12)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 2,
        )

    return out