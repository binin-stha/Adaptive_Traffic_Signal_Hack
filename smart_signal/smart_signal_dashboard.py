"""
Smart Signal — Adaptive Traffic Light Dashboard
================================================
Single-file Streamlit application.

Run:
    pip install -r requirements.txt
    streamlit run smart_signal_dashboard.py
"""

from PIL import Image
import json
import math
import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import streamlit as st
from streamlit_drawable_canvas import st_canvas

# ─────────────────────────────────────────────────────────────────────────────
# 1. CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

DIRECTIONS: List[str] = ["north", "south", "east", "west"]

DIR_COLORS: Dict[str, str] = {
    "north": "#3B82F6",
    "south": "#22C55E",
    "east": "#F59E0B",
    "west": "#EC4899",
}

CATEGORY_MAP: Dict[str, str] = {
    "person": "pedestrian",
    "bicycle": "vehicle",
    "car": "vehicle",
    "motorcycle": "vehicle",
    "bus": "vehicle",
    "truck": "vehicle",
}

BBOX_COLORS: Dict[str, Tuple[int, int, int]] = {
    "vehicle": (0, 200, 80),
    "pedestrian": (60, 60, 255),
    "pedestrian_crossing": (0, 140, 255),
}

SHAPE_COLORS: Dict[str, Tuple[int, int, int]] = {
    "lane": (255, 220, 0),
    "zebra_crossing": (255, 0, 220),
    "stop_line": (0, 180, 255),
    "count_line": (0, 255, 255),
}

# Decision engine defaults
WEIGHTS = {"vehicle": 1.5, "pedestrian": 1.2}
BASE_TIME = 10
MIN_GREEN = 10
MAX_GREEN = 60
MAX_WAIT = 90
SPEED_THRESH_DEFAULT = 3.0

CANVAS_HEIGHT = 480

# ─────────────────────────────────────────────────────────────────────────────
# 2. THEME (injected CSS)
# ─────────────────────────────────────────────────────────────────────────────

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

.stApp {
    background-color: #060B14;
    color: #F1F5F9;
    font-family: 'Inter', sans-serif;
}
.block-container { padding-top: 1.2rem; max-width: 1500px; }

h1,h2,h3,h4 { font-family: 'Inter', sans-serif; color: #F1F5F9; letter-spacing: -0.02em; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 2px; background: #0D1420; border-radius: 12px;
    padding: 4px; border: 1px solid #1E293B;
}
.stTabs [data-baseweb="tab"] {
    background: transparent; border: none; border-radius: 8px;
    color: #94A3B8; font-size: 13px; font-weight: 500;
    padding: 10px 22px; transition: all 0.2s;
}
.stTabs [data-baseweb="tab"]:hover { background: #1C2A3E; color: #F1F5F9; }
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    background: #3B82F6; color: #fff;
}
.stTabs [data-baseweb="tab-highlight"] { display: none; }

/* Buttons */
.stButton > button {
    background: #141E2E; color: #F1F5F9; border: 1px solid #334155;
    border-radius: 8px; padding: 8px 18px; font-size: 13px;
    font-weight: 500; transition: all 0.2s;
}
.stButton > button:hover { background: #1C2A3E; border-color: #3B82F6; }
.stButton > button[kind="primary"] { background: #3B82F6; border-color: #3B82F6; color: #fff; }
.stButton > button[kind="primary"]:hover { background: #60A5FA; }

/* Metrics */
[data-testid="stMetric"] {
    background: #0D1420; border: 1px solid #1E293B;
    border-radius: 12px; padding: 16px;
}
[data-testid="stMetricLabel"] { color: #64748B; font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; }
[data-testid="stMetricValue"] { color: #F1F5F9; font-family: 'JetBrains Mono', monospace; font-size: 24px; }

/* Inputs */
.stSelectbox > div > div, .stTextInput > div > div > input,
.stNumberInput > div > div > input {
    background: #141E2E; color: #F1F5F9; border: 1px solid #1E293B;
    border-radius: 8px; font-size: 13px;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0D1420 0%, #060B14 100%);
    border-right: 1px solid #1E293B;
}

/* Alerts */
[data-testid="stAlert"] { border-radius: 10px; }

/* Scrollbar */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: #0D1420; }
::-webkit-scrollbar-thumb { background: #334155; border-radius: 99px; }

hr { border: none; border-top: 1px solid #1E293B; }
</style>
"""

# ─────────────────────────────────────────────────────────────────────────────
# 3. SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────

def init_state() -> None:
    """Initialise all session-state keys once."""
    if "config" not in st.session_state:
        st.session_state.config = {
            d: {
                "media_bytes": None,
                "media_type": None,
                "frame": None,
                "scale": 1.0,
                "shapes": [],
            }
            for d in DIRECTIONS
        }
    if "track_history" not in st.session_state:
        st.session_state.track_history = defaultdict(lambda: deque(maxlen=15))
    if "signal_state" not in st.session_state:
        st.session_state.signal_state = {d: "red" for d in DIRECTIONS}
    if "wait_times" not in st.session_state:
        st.session_state.wait_times = {d: 0.0 for d in DIRECTIONS}
    if "last_run" not in st.session_state:
        st.session_state.last_run = None


# ─────────────────────────────────────────────────────────────────────────────
# 4. MODEL LOADING
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_resource
def load_model():
    """Load YOLOv8n once, cache across reruns."""
    from ultralytics import YOLO
    return YOLO("yolov8n.pt")


# ─────────────────────────────────────────────────────────────────────────────
# 5. GEOMETRY HELPERS
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# 6. CANVAS SHAPE PARSING
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# 7. DETECTION + TRACKING
# ─────────────────────────────────────────────────────────────────────────────

def classify_motion(
    track_id: int,
    center: Tuple[float, float],
    thresh: float,
) -> str:
    """Classify a tracked object as moving / waiting based on displacement."""
    hist = st.session_state.track_history[track_id]
    hist.append(center)
    if len(hist) < 5:
        return "unknown"
    dx = hist[-1][0] - hist[0][0]
    dy = hist[-1][1] - hist[0][1]
    speed = math.sqrt(dx * dx + dy * dy) / len(hist)
    return "moving" if speed > thresh else "waiting"


def run_tracking(
    frame: np.ndarray,
    model,
    conf: float = 0.25,
    imgsz: int = 1280,
    speed_thresh: float = SPEED_THRESH_DEFAULT,
) -> List[Dict[str, Any]]:
    """Run YOLOv8 + ByteTrack on a single frame. Returns detection dicts."""
    results = model.track(
        frame,
        conf=conf,
        imgsz=imgsz,
        iou=0.45,
        persist=True,
        tracker="bytetrack.yaml",
        verbose=False,
    )[0]

    dets: List[Dict[str, Any]] = []
    if results.boxes is None or results.boxes.id is None:
        return dets

    for box in results.boxes:
        cls_name = model.names[int(box.cls[0])]
        if cls_name not in CATEGORY_MAP:
            continue

        tid = int(box.id[0])
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        center = ((x1 + x2) / 2, (y1 + y2) / 2)
        state = classify_motion(tid, center, speed_thresh)

        dets.append(
            {
                "track_id": tid,
                "class_name": cls_name,
                "category": CATEGORY_MAP[cls_name],
                "bbox": [x1, y1, x2, y2],
                "center": center,
                "confidence": float(box.conf[0]),
                "state": state,
            }
        )

    return dets


# ─────────────────────────────────────────────────────────────────────────────
# 8. LANE / CROSSING ASSIGNMENT
# ─────────────────────────────────────────────────────────────────────────────

def assign_to_shapes(
    dets: List[Dict[str, Any]],
    shapes: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Tag each detection with the lane / crossing / count-line it falls in."""
    lanes = [s for s in shapes if s["label"] == "lane"]
    crossings = [s for s in shapes if s["label"] == "zebra_crossing"]
    count_lines = [s for s in shapes if s["label"] == "count_line"]

    for d in dets:
        d["lane_id"] = None
        d["in_crossing"] = False
        d["crossed_count_line"] = False

        # Lane assignment (point-in-polygon)
        for lane in lanes:
            if point_in_polygon(d["center"], lane["points"]):
                d["lane_id"] = lane["id"]
                break

        # Crossing assignment
        for cx in crossings:
            if point_in_polygon(d["center"], cx["points"]):
                d["in_crossing"] = True
                break

        # Count-line crossing (check if track moved across the line)
        hist = st.session_state.track_history.get(d["track_id"])
        if hist and len(hist) >= 2:
            prev = hist[-2]
            curr = hist[-1]
            for cl in count_lines:
                if len(cl["points"]) == 2:
                    if crossed_line(prev, curr, cl["points"][0], cl["points"][1]):
                        d["crossed_count_line"] = True
                        break

    return dets


# ─────────────────────────────────────────────────────────────────────────────
# 9. COUNTING
# ─────────────────────────────────────────────────────────────────────────────

def counts_for_direction(
    dets: List[Dict[str, Any]],
    shapes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Count vehicles (incoming + focus lanes only) and pedestrians."""
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


# ─────────────────────────────────────────────────────────────────────────────
# 10. DECISION ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def compute_green_times(
    counts: Dict[str, Dict[str, Any]],
    wait_times: Dict[str, float],
) -> Tuple[Dict[str, float], str]:
    """Rule-based adaptive green-time computation."""
    load: Dict[str, float] = {}
    for d in counts:
        load[d] = (
            counts[d]["vehicle"] * WEIGHTS["vehicle"]
            + counts[d]["pedestrian"] * WEIGHTS["pedestrian"]
        )

    total = sum(load.values()) or 1.0
    result: Dict[str, float] = {}

    for d in counts:
        # Starvation guard
        if wait_times.get(d, 0) > MAX_WAIT:
            result[d] = float(MAX_GREEN)
            continue
        if load[d] == 0:
            result[d] = 0.0
            continue
        share = BASE_TIME + (load[d] / total) * (MAX_GREEN - BASE_TIME)
        result[d] = float(max(MIN_GREEN, min(MAX_GREEN, round(share))))

    top = max(load, key=load.get)
    reason = (
        f"{top.upper()} gets extended green — "
        f"highest weighted load ({load[top]:.1f})"
    )
    return result, reason


def set_signal_state(active_direction: Optional[str]) -> None:
    for d in st.session_state.signal_state:
        st.session_state.signal_state[d] = (
            "green" if d == active_direction else "red"
        )


def check_violations(
    direction: str,
    dets: List[Dict[str, Any]],
) -> List[int]:
    """Flag pedestrians actively crossing while their signal is green."""
    if st.session_state.signal_state.get(direction) != "green":
        return []
    return [
        d["track_id"]
        for d in dets
        if d["category"] == "pedestrian"
        and d.get("in_crossing")
        and d["state"] == "moving"
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 11. FRAME ANNOTATION
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# 12. UI — ANNOTATION PANEL (per direction)
# ─────────────────────────────────────────────────────────────────────────────

def annotation_panel(direction: str) -> None:
    """Full annotation workflow for one direction — pen-tool polygon drawing
    directly on the uploaded frame."""
    cfg = st.session_state.config[direction]
    accent = DIR_COLORS[direction]

    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
            <div style="width:4px;height:28px;border-radius:4px;background:{accent};"></div>
            <div>
                <div style="font-size:17px;font-weight:700;color:#F1F5F9;">
                    {direction.upper()} APPROACH
                </div>
                <div style="font-size:11px;color:#64748B;text-transform:uppercase;letter-spacing:0.06em;">
                    Upload frame, then click vertices to draw lanes / crossing / lines
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Upload ────────────────────────────────────────────────────────────
    uploaded = st.file_uploader(
        f"Upload image or video — {direction.title()}",
        type=["jpg", "jpeg", "png", "mp4", "mov", "avi"],
        key=f"upload_{direction}",
    )

    if uploaded is not None:
        is_video = uploaded.type and uploaded.type.startswith("video")
        cfg["media_type"] = "video" if is_video else "image"

        if is_video:
            tmp = f"/tmp/ss_{direction}_{uploaded.name}"
            with open(tmp, "wb") as f:
                f.write(uploaded.getbuffer())
            cap = cv2.VideoCapture(tmp)
            ok, frame = cap.read()
            cap.release()
            if not ok:
                st.error("Could not read the first frame of this video.")
                return
            cfg["media_bytes"] = tmp
        else:
            buf = np.frombuffer(uploaded.getbuffer(), np.uint8)
            frame = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            if frame is None:
                st.error("Could not decode this image.")
                return
            cfg["media_bytes"] = uploaded.getbuffer()

        cfg["frame"] = frame

    if cfg["frame"] is None:
        st.info("Upload media to begin drawing.")
        return

    frame = cfg["frame"]
    h, w = frame.shape[:2]
    scale = CANVAS_HEIGHT / h
    cfg["scale"] = scale
    disp_w = int(w * scale)
    disp_h = CANVAS_HEIGHT

    # Convert frame to RGB for canvas background (PIL-compatible numpy array)
    bg_rgb = cv2.cvtColor(cv2.resize(frame, (disp_w, disp_h)), cv2.COLOR_BGR2RGB)
    bg_pil = Image.fromarray(bg_rgb) 

    # ── Tool selection ────────────────────────────────────────────────────
    col_tools, col_props = st.columns([3, 2])

    with col_tools:
        draw_choice = st.radio(
            "Annotation tool",
            [
                "Lane (polygon — click vertices, double-click to close)",
                "Zebra crossing (polygon — click vertices, double-click to close)",
                "Stop line (line — click start, click end)",
                "Count line (line — click start, click end)",
            ],
            key=f"drawmode_{direction}",
        )

        # Determine fabric.js drawing mode
        if "polygon" in draw_choice:
            fabric_mode = "polygon"
        else:
            fabric_mode = "line"

        st.caption(
            "Polygon: click to place each vertex. Double-click to close the shape. "
            "Line: click start point, then click end point."
        )

        # ── THE CANVAS — background is the actual uploaded frame ──────────
        canvas_result = st_canvas(
            fill_color="rgba(255, 200, 0, 0.15)",
            stroke_width=3,
            stroke_color=accent,
            background_image=bg_pil,
            update_streamlit=True,
            height=disp_h,
            width=disp_w,
            drawing_mode=fabric_mode,
            key=f"canvas_{direction}_{draw_choice}",
            background_color="#111827",
            point_display_radius=5,
        )

    # ── Shape properties (right column) ───────────────────────────────────
    with col_props:
        st.markdown(
            '<div style="font-size:13px;font-weight:600;color:#94A3B8;'
            'margin-bottom:12px;">SHAPE PROPERTIES</div>',
            unsafe_allow_html=True,
        )

        # Auto-detect label from tool choice
        if "Lane" in draw_choice:
            shape_label = "lane"
        elif "Zebra" in draw_choice:
            shape_label = "zebra_crossing"
        elif "Stop" in draw_choice:
            shape_label = "stop_line"
        else:
            shape_label = "count_line"

        st.markdown(
            f'<div style="font-size:12px;color:#CBD5E1;margin-bottom:12px;">'
            f"Type: <b>{shape_label}</b></div>",
            unsafe_allow_html=True,
        )

        lane_id = side = travel = None
        is_focus = False

        if shape_label == "lane":
            lane_id = st.text_input(
                "Lane ID",
                value=f"{direction}_lane_{len([s for s in cfg['shapes'] if s['label'] == 'lane']) + 1}",
                key=f"laneid_{direction}",
            )
            side = st.selectbox(
                "Approach side",
                DIRECTIONS,
                index=DIRECTIONS.index(direction),
                key=f"side_{direction}",
            )
            travel = st.selectbox(
                "Vehicle travel direction",
                ["incoming", "outgoing"],
                key=f"travel_{direction}",
            )
            is_focus = st.checkbox(
                "Focus lane (feeds signal decision)",
                value=True,
                key=f"focus_{direction}",
            )
        elif shape_label == "zebra_crossing":
            st.caption(
                "Draw the full zebra crossing area as a polygon. "
                "Pedestrians inside this zone are tracked for crossing detection."
            )
        elif shape_label == "stop_line":
            st.caption(
                "Click two points to define the stop line. "
                "Vehicles behind this line are considered waiting."
            )
        elif shape_label == "count_line":
            st.caption(
                "Click two points to define a counting line. "
                "Vehicles crossing this line are counted."
            )

        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

        if st.button(
            "Save shape", key=f"save_{direction}", use_container_width=True
        ):
            parsed = parse_canvas_objects(
                canvas_result.json_data if canvas_result else None,
                scale,
            )
            if not parsed:
                st.warning(
                    "No shape detected. Draw on the image above first — "
                    "click vertices for polygon, or two points for a line."
                )
            else:
                shape = parsed[-1]  # take the most recent shape
                entry: Dict[str, Any] = {
                    "label": shape_label,
                    "points": shape["points"],
                }
                if shape_label == "lane":
                    entry.update(
                        {
                            "id": lane_id,
                            "side": side,
                            "travel": travel,
                            "focus": is_focus,
                        }
                    )
                cfg["shapes"].append(entry)
                st.success(f"Saved {shape_label}.")

        # ── Saved shapes list ─────────────────────────────────────────────
        st.markdown(
            '<div style="font-size:13px;font-weight:600;color:#94A3B8;'
            'margin:20px 0 8px;">SAVED SHAPES</div>',
            unsafe_allow_html=True,
        )

        if not cfg["shapes"]:
            st.caption("No shapes saved yet. Draw and save above.")
        else:
            for i, s in enumerate(cfg["shapes"]):
                if s["label"] == "lane":
                    desc = (
                        f"{s.get('id', '?')} — "
                        f"{s.get('side', '?')}/{s.get('travel', '?')}"
                        f"{'  [FOCUS]' if s.get('focus') else ''}"
                    )
                elif s["label"] == "zebra_crossing":
                    desc = f"Zebra crossing ({len(s['points'])} vertices)"
                elif s["label"] == "stop_line":
                    desc = "Stop line"
                elif s["label"] == "count_line":
                    desc = "Count line"
                else:
                    desc = s["label"]

                c1, c2 = st.columns([5, 1])
                c1.markdown(
                    f'<div style="font-size:12px;color:#CBD5E1;padding:4px 0;">'
                    f"{i + 1}. {desc}</div>",
                    unsafe_allow_html=True,
                )
                if c2.button("x", key=f"del_{direction}_{i}"):
                    cfg["shapes"].pop(i)
                    st.rerun()

    # ── Preview: frame with all saved shapes overlaid ─────────────────────
    if cfg["shapes"]:
        st.markdown(
            '<div style="font-size:13px;font-weight:600;color:#94A3B8;'
            'margin:16px 0 8px;">ANNOTATION PREVIEW</div>',
            unsafe_allow_html=True,
        )
        preview = annotate_frame(frame, [], cfg["shapes"])
        st.image(
            cv2.cvtColor(preview, cv2.COLOR_BGR2RGB),
            caption=f"{direction.upper()} — saved annotations overlaid",
            use_column_width=True,
        )

# ─────────────────────────────────────────────────────────────────────────────
# 13. UI — ANALYSIS TAB
# ─────────────────────────────────────────────────────────────────────────────

def analysis_tab() -> None:
    st.markdown(
        '<div style="font-size:17px;font-weight:700;color:#F1F5F9;'
        'margin-bottom:4px;">Analysis</div>'
        '<div style="font-size:11px;color:#64748B;text-transform:uppercase;'
        'letter-spacing:0.06em;margin-bottom:16px;">'
        "Run detection, tracking, and signal decision across all approaches</div>",
        unsafe_allow_html=True,
    )

    # Settings row
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        speed_thresh = st.slider(
            "Motion threshold (px/frame)",
            0.5, 15.0, SPEED_THRESH_DEFAULT, 0.5,
            help="Raise if stationary objects flicker between moving/waiting",
        )
    with col_b:
        conf_thresh = st.slider("Detection confidence", 0.1, 0.9, 0.25, 0.05)
    with col_c:
        imgsz = st.selectbox("Inference size", [640, 960, 1280], index=2)

    if st.button("Run detection on all directions", type="primary", use_container_width=True):
        model = load_model()
        results_by_dir: Dict[str, Dict] = {}
        counts_by_dir: Dict[str, Dict] = {}

        progress = st.progress(0, text="Initialising...")

        for idx, direction in enumerate(DIRECTIONS):
            cfg = st.session_state.config[direction]
            if cfg["frame"] is None:
                continue

            progress.progress(
                (idx) / len(DIRECTIONS),
                text=f"Processing {direction.upper()}...",
            )

            frame = cfg["frame"]
            dets = run_tracking(
                frame, model,
                conf=conf_thresh,
                imgsz=imgsz,
                speed_thresh=speed_thresh,
            )
            dets = assign_to_shapes(dets, cfg["shapes"])
            counts = counts_for_direction(dets, cfg["shapes"])
            annotated = annotate_frame(frame, dets, cfg["shapes"])

            results_by_dir[direction] = {"dets": dets, "annotated": annotated}
            counts_by_dir[direction] = counts

        progress.progress(1.0, text="Done.")

        if not counts_by_dir:
            st.warning("No directions have uploaded media.")
            return

        # ── Decision ──────────────────────────────────────────────────────
        green_times, reason = compute_green_times(
            counts_by_dir, st.session_state.wait_times
        )
        top_dir = max(green_times, key=green_times.get)
        set_signal_state(top_dir if green_times[top_dir] > 0 else None)
        st.session_state.last_run = datetime.now()

        # ── Decision summary ──────────────────────────────────────────────
        st.markdown(
            '<div style="font-size:14px;font-weight:600;color:#94A3B8;'
            'margin:20px 0 8px;">SIGNAL DECISION</div>',
            unsafe_allow_html=True,
        )
        st.success(reason)

        # Green-time metrics row
        gt_cols = st.columns(len(green_times))
        for col, (d, gt) in zip(gt_cols, green_times.items()):
            with col:
                sig = st.session_state.signal_state[d]
                sig_color = "#22C55E" if sig == "green" else "#EF4444"
                st.markdown(
                    f"""
                    <div style="
                        background:#0D1420;border:1px solid #1E293B;
                        border-top:3px solid {DIR_COLORS[d]};
                        border-radius:12px;padding:16px;text-align:center;
                    ">
                        <div style="font-size:11px;color:#64748B;text-transform:uppercase;letter-spacing:0.06em;">
                            {d.upper()}
                        </div>
                        <div style="font-size:28px;font-weight:700;color:#F1F5F9;
                            font-family:'JetBrains Mono',monospace;margin:6px 0;">
                            {gt:.0f}s
                        </div>
                        <div style="
                            display:inline-flex;align-items:center;gap:5px;
                            padding:2px 10px;border-radius:99px;
                            background:rgba({'34,197,94' if sig == 'green' else '239,68,68'},0.12);
                            border:1px solid rgba({'34,197,94' if sig == 'green' else '239,68,68'},0.3);
                        ">
                            <div style="width:7px;height:7px;border-radius:50%;background:{sig_color};"></div>
                            <span style="font-size:11px;color:{sig_color};font-weight:600;">
                                {sig.upper()}
                            </span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # ── Per-direction detail ──────────────────────────────────────────
        st.markdown(
            '<div style="font-size:14px;font-weight:600;color:#94A3B8;'
            'margin:24px 0 8px;">PER-APPROACH DETAIL</div>',
            unsafe_allow_html=True,
        )

        detail_cols = st.columns(len(results_by_dir))
        for col, (direction, r) in zip(detail_cols, results_by_dir.items()):
            with col:
                st.image(
                    cv2.cvtColor(r["annotated"], cv2.COLOR_BGR2RGB),
                    caption=direction.upper(),
                    use_column_width=True,
                )

                c = counts_by_dir[direction]
                st.markdown(
                    f"""
                    <div style="font-size:12px;color:#CBD5E1;line-height:1.8;">
                        Vehicles: <b>{c['vehicle']}</b>
                        &nbsp;(waiting: {c['waiting_vehicles']})<br/>
                        Pedestrians: <b>{c['pedestrian']}</b>
                        &nbsp;(waiting: {c['waiting_pedestrians']},
                        crossing: {c['crossing_pedestrians']})<br/>
                        Count-line crossings: <b>{c['count_line_crossings']}</b>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                violations = check_violations(direction, r["dets"])
                if violations:
                    st.error(
                        f"VIOLATION — pedestrian(s) {violations} "
                        f"crossing on GREEN at {direction.upper()}"
                    )

    # ── Layout save / load ────────────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        '<div style="font-size:14px;font-weight:600;color:#94A3B8;'
        'margin-bottom:8px;">LAYOUT CONFIG</div>',
        unsafe_allow_html=True,
    )

    export_data = {
        d: st.session_state.config[d]["shapes"] for d in DIRECTIONS
    }
    st.download_button(
        "Download layout as JSON",
        json.dumps(export_data, default=str, indent=2),
        file_name="smart_signal_layout.json",
        mime="application/json",
    )

    uploaded_cfg = st.file_uploader(
        "Load a saved layout JSON", type=["json"], key="cfg_upload"
    )
    if uploaded_cfg is not None and st.button("Apply loaded layout"):
        loaded = json.load(uploaded_cfg)
        for d in DIRECTIONS:
            if d in loaded:
                st.session_state.config[d]["shapes"] = loaded[d]
        st.success("Layout applied. Re-upload media per direction.")


# ─────────────────────────────────────────────────────────────────────────────
# 14. UI — INTERSECTION OVERVIEW (sidebar)
# ─────────────────────────────────────────────────────────────────────────────

def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            """
            <div style="padding:8px 0 16px;border-bottom:1px solid #1E293B;margin-bottom:16px;">
                <div style="font-size:17px;font-weight:700;color:#F1F5F9;letter-spacing:-0.02em;">
                    Smart Signal
                </div>
                <div style="font-size:11px;color:#64748B;text-transform:uppercase;letter-spacing:0.06em;">
                    Adaptive Traffic Management
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Signal state indicators
        st.markdown(
            '<div style="font-size:11px;font-weight:600;color:#64748B;'
            'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;">'
            "Signal State</div>",
            unsafe_allow_html=True,
        )

        for d in DIRECTIONS:
            sig = st.session_state.signal_state[d]
            dot_color = "#22C55E" if sig == "green" else "#EF4444"
            st.markdown(
                f"""
                <div style="
                    display:flex;align-items:center;gap:8px;
                    padding:6px 10px;margin-bottom:4px;
                    background:#0D1420;border:1px solid #1E293B;
                    border-radius:8px;border-left:3px solid {DIR_COLORS[d]};
                ">
                    <div style="width:8px;height:8px;border-radius:50%;
                        background:{dot_color};
                        box-shadow:0 0 6px {dot_color};"></div>
                    <span style="font-size:12px;color:#CBD5E1;font-weight:500;">
                        {d.upper()}
                    </span>
                    <span style="font-size:11px;color:{dot_color};font-weight:600;margin-left:auto;">
                        {sig.upper()}
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Annotation progress
        st.markdown(
            '<div style="font-size:11px;font-weight:600;color:#64748B;'
            'text-transform:uppercase;letter-spacing:0.08em;'
            'margin:16px 0 8px;">Annotation Progress</div>',
            unsafe_allow_html=True,
        )

        for d in DIRECTIONS:
            cfg = st.session_state.config[d]
            has_media = cfg["frame"] is not None
            n_shapes = len(cfg["shapes"])
            n_lanes = len([s for s in cfg["shapes"] if s["label"] == "lane"])
            has_crossing = any(
                s["label"] == "zebra_crossing" for s in cfg["shapes"]
            )

            status_parts = []
            if has_media:
                status_parts.append("media")
            if n_lanes > 0:
                status_parts.append(f"{n_lanes} lane(s)")
            if has_crossing:
                status_parts.append("crossing")

            status = ", ".join(status_parts) if status_parts else "not configured"
            dot = "#22C55E" if (has_media and n_lanes > 0) else "#64748B"

            st.markdown(
                f"""
                <div style="display:flex;align-items:center;gap:6px;padding:3px 0;">
                    <div style="width:6px;height:6px;border-radius:50%;background:{dot};"></div>
                    <span style="font-size:11px;color:#94A3B8;">
                        {d.upper()}: {status}
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Last run
        if st.session_state.last_run:
            st.markdown(
                f'<div style="font-size:11px;color:#64748B;margin-top:16px;">'
                f"Last analysis: {st.session_state.last_run.strftime('%H:%M:%S')}"
                f"</div>",
                unsafe_allow_html=True,
            )


# ─────────────────────────────────────────────────────────────────────────────
# 15. MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(
        page_title="Smart Signal — Adaptive Traffic Dashboard",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    init_state()

    st.markdown(
        """
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
            <div>
                <span style="font-size:20px;font-weight:700;color:#F1F5F9;letter-spacing:-0.02em;">
                    Smart Signal
                </span>
                <span style="font-size:12px;color:#64748B;margin-left:12px;">
                    Adaptive Traffic Light Dashboard
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_sidebar()

    tabs = st.tabs([d.upper() for d in DIRECTIONS] + ["Analysis"])

    for tab, direction in zip(tabs[:4], DIRECTIONS):
        with tab:
            annotation_panel(direction)

    with tabs[4]:
        analysis_tab()


if __name__ == "__main__":
    main()