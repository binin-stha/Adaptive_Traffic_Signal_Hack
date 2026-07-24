"""YOLOv8 model loading, tracking, and motion classification."""

import math
from collections import defaultdict, deque
from typing import Any, Dict, List, Tuple

import numpy as np
import streamlit as st


# ─────────────────────────────────────────────────────────────────────────────
# MODEL
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_resource
def load_model():
    """Load YOLOv8n once. Downloads ~6 MB on first run, then caches."""
    from ultralytics import YOLO
    model = YOLO("yolov8n.pt")
    return model


# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY MAPPING  (COCO → project categories)
# ─────────────────────────────────────────────────────────────────────────────

CATEGORY_MAP: Dict[str, str] = {
    "person": "pedestrian",
    "bicycle": "vehicle",
    "car": "vehicle",
    "motorcycle": "vehicle",
    "bus": "vehicle",
    "truck": "vehicle",
}


# ─────────────────────────────────────────────────────────────────────────────
# MOTION CLASSIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def _get_track_history() -> defaultdict:
    """Persistent per-track position history (survives reruns via session_state)."""
    if "track_history" not in st.session_state:
        st.session_state.track_history = defaultdict(lambda: deque(maxlen=15))
    return st.session_state.track_history


def classify_motion(
    track_id: int,
    center: Tuple[float, float],
    thresh: float,
) -> str:
    """Classify a tracked object as moving / waiting / unknown.

    Uses displacement over the last N frames stored in a per-track deque.
    """
    hist = _get_track_history()[track_id]
    hist.append(center)

    if len(hist) < 5:
        return "unknown"

    dx = hist[-1][0] - hist[0][0]
    dy = hist[-1][1] - hist[0][1]
    speed = math.sqrt(dx * dx + dy * dy) / len(hist)
    return "moving" if speed > thresh else "waiting"


# ─────────────────────────────────────────────────────────────────────────────
# DETECTION + TRACKING
# ─────────────────────────────────────────────────────────────────────────────

def run_tracking(
    frame: np.ndarray,
    model,
    conf: float = 0.25,
    imgsz: int = 1280,
    speed_thresh: float = 3.0,
) -> List[Dict[str, Any]]:
    """Run YOLOv8 + ByteTrack on a single frame.

    Returns a list of detection dicts:
        track_id, class_name, category, bbox, center, confidence, state
    """
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
        center = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
        state = classify_motion(tid, center, speed_thresh)

        dets.append({
            "track_id": tid,
            "class_name": cls_name,
            "category": CATEGORY_MAP[cls_name],
            "bbox": [x1, y1, x2, y2],
            "center": center,
            "confidence": float(box.conf[0]),
            "state": state,
        })

    return dets


def reset_tracking() -> None:
    """Clear all track histories (call when switching videos / resetting)."""
    if "track_history" in st.session_state:
        st.session_state.track_history.clear()