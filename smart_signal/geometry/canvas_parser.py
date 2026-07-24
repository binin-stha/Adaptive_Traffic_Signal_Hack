"""
Canvas parser module for Smart Signal — parses canvas objects from streamlit-drawable-canvas.
"""
from typing import Any, Dict, List, Optional


def parse_canvas_objects(
    json_data: Optional[dict],
    scale: float,
) -> List[Dict[str, Any]]:
    """Parse fabric.js objects from streamlit-drawable-canvas into
    normalised shape dicts in original-frame pixel coordinates."""
    if not json_data or "objects" not in json_data:
        return []

    parsed: List[Dict[str, Any]] = []
    for obj in json_data["objects"]:
        left = obj.get("left", 0)
        top = obj.get("top", 0)
        sx = obj.get("scaleX", 1)
        sy = obj.get("scaleY", 1)

        if obj.get("type") == "polygon" and "points" in obj:
            pts = [
                (
                    (p["x"] * sx + left) / scale,
                    (p["y"] * sy + top) / scale,
                )
                for p in obj["points"]
            ]
            parsed.append({"kind": "polygon", "points": pts})

        elif obj.get("type") == "line":
            x1 = (obj.get("x1", 0) + left) / scale
            y1 = (obj.get("y1", 0) + top) / scale
            x2 = (obj.get("x2", 0) + left) / scale
            y2 = (obj.get("y2", 0) + top) / scale
            parsed.append({"kind": "line", "points": [(x1, y1), (x2, y2)]})

        elif obj.get("type") == "path":
            # freehand path — collect all path points
            path_pts = []
            for segment in obj.get("path", []):
                if len(segment) >= 3:
                    path_pts.append(
                        (
                            (segment[1] * sx + left) / scale,
                            (segment[2] * sy + top) / scale,
                        )
                    )
            if len(path_pts) >= 2:
                parsed.append({"kind": "line", "points": [path_pts[0], path_pts[-1]]})

    return parsed