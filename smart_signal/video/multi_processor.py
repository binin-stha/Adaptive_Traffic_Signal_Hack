"""Synchronized multi-direction video processing."""

from typing import Any, Dict, Optional

import cv2
import streamlit as st

from config.constants import DIRECTIONS, SPEED_THRESH_DEFAULT
from models.detector import load_model, run_tracking
from geometry.assignment import assign_to_shapes, counts_for_direction
from engine.decision_flow import DecisionFlow

from geometry.assignment import assign_to_shapes, counts_for_direction, filter_to_lanes
from tracking.pedestrian_wait import PedestrianWaitTracker

class MultiVideoProcessor:
    """Opens all four direction videos and advances them in lockstep."""

    def __init__(self):
        self.caps: Dict[str, cv2.VideoCapture] = {}
        self.frame_idx = 0
        self.total_frames = 0
        self.fps = 30.0
        self.finished = False
        self.decision = DecisionFlow()
        self.ped_wait = PedestrianWaitTracker()

    def open_all(self, paths: Dict[str, str]) -> bool:
        for d, path in paths.items():
            cap = cv2.VideoCapture(path)
            if cap.isOpened():
                self.caps[d] = cap
        if not self.caps:
            return False
        first = next(iter(self.caps.values()))
        self.total_frames = int(first.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = first.get(cv2.CAP_PROP_FPS) or 30.0
        return True

    def tick(self, model, conf, imgsz, speed_thresh) -> Optional[Dict[str, Any]]:
        """Advance every video by one frame and run the full pipeline."""
        frames = {}
        any_read = False
        for d, cap in self.caps.items():
            ret, frame = cap.read()
            if ret:
                frames[d] = frame
                any_read = True

        if not any_read:
            self.finished = True
            return None

        self.frame_idx += 1
        dt = 1.0 / self.fps

        per_dir: Dict[str, Dict[str, Any]] = {}
        counts_by_dir: Dict[str, Dict[str, Any]] = {}

        for d, frame in frames.items():
            shapes = st.session_state.config[d]["shapes"]

            dets = run_tracking(frame, model, conf=conf, imgsz=imgsz,
                                speed_thresh=speed_thresh)
            dets = filter_to_lanes(dets, shapes)
            dets = self.ped_wait.update(dets, shapes, dt)
            track_hist = st.session_state.get("track_history", {})
            dets = assign_to_shapes(dets, shapes, track_hist)
            counts = counts_for_direction(dets, shapes)

            per_dir[d] = {"dets": dets, "frame": frame, "shapes": shapes}
            counts_by_dir[d] = counts

        # Run the transparent decision engine on aggregated counts.
        decision = self.decision.evaluate(counts_by_dir, dt)

        return {
            "frame_idx": self.frame_idx,
            "total_frames": self.total_frames,
            "fps": self.fps,
            "per_dir": per_dir,
            "counts_by_dir": counts_by_dir,
            "decision": decision,
        }

    def release(self):
        for cap in self.caps.values():
            cap.release()
        self.caps = {}


def get_multi_processor() -> Optional[MultiVideoProcessor]:
    return st.session_state.get("multi_proc")


def init_multi_processor(paths: Dict[str, str]) -> Optional[MultiVideoProcessor]:
    proc = MultiVideoProcessor()
    if proc.open_all(paths):
        st.session_state.multi_proc = proc
        return proc
    return None


def cleanup_multi_processor():
    proc = get_multi_processor()
    if proc:
        proc.release()
    st.session_state.pop("multi_proc", None)