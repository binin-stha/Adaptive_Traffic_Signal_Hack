"""Synchronized multi-direction processing over any frame source."""

from typing import Any, Dict, Optional

import streamlit as st

from config.constants import DIRECTIONS, SPEED_THRESH_DEFAULT
from models.detector import run_tracking
from geometry.assignment import assign_to_shapes, counts_for_direction, filter_to_lanes
from tracking.pedestrian_wait import PedestrianWaitTracker
from engine.decision_flow import DecisionFlow
from video.sources import FrameSource, ImageSource, VideoSource, CameraSource


class MultiVideoProcessor:
    """Advances every direction's source in lockstep and runs the pipeline."""

    def __init__(self):
        self.sources: Dict[str, FrameSource] = {}
        self.mode = "video"
        self.frame_idx = 0
        self.total_frames = 0
        self.fps = 30.0
        self.finished = False
        self.decision = DecisionFlow()
        self.ped_wait = PedestrianWaitTracker()

    def open(self, sources: Dict[str, FrameSource], mode: str) -> bool:
        self.sources = dict(sources)
        if not self.sources:
            return False
        self.mode = mode
        self.fps = min(s.fps for s in self.sources.values()) or 30.0
        if all(s.is_finite for s in self.sources.values()):
            self.total_frames = min(s.total_frames for s in self.sources.values())
        else:
            self.total_frames = 0  # image / live run until paused
        return True

    def tick(self, model, conf, imgsz, speed_thresh) -> Optional[Dict[str, Any]]:
        frames = {}
        for d, src in self.sources.items():
            ret, frame = src.read()
            if ret and frame is not None:
                frames[d] = frame

        if not frames:
            self.finished = True
            return None

        self.frame_idx += 1
        dt = 1.0 / self.fps

        per_dir = {}
        counts_by_dir = {}

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

        decision = self.decision.evaluate(counts_by_dir, dt)

        return {
            "mode": self.mode,
            "frame_idx": self.frame_idx,
            "total_frames": self.total_frames,
            "fps": self.fps,
            "per_dir": per_dir,
            "counts_by_dir": counts_by_dir,
            "decision": decision,
        }

    def release(self):
        for src in self.sources.values():
            src.release()
        self.sources = {}


# ── session helpers ────────────────────────────────────────────────────────────

def build_sources(mode: str) -> Dict[str, FrameSource]:
    """Create a frame source per active direction for the given mode."""
    active = st.session_state.get("active_directions", list(DIRECTIONS))
    sources: Dict[str, FrameSource] = {}

    for d in active:
        cfg = st.session_state.config[d]
        if mode == "image" and cfg["media_type"] == "image" and cfg["frame"] is not None:
            sources[d] = ImageSource(cfg["frame"])
        elif mode == "video" and cfg["media_type"] == "video" and cfg["media_bytes"]:
            sources[d] = VideoSource(cfg["media_bytes"])
        elif mode == "live":
            idx = st.session_state.get(f"cam_index_{d}", 0)
            sources[d] = CameraSource(idx)

    return sources


def get_multi_processor() -> Optional[MultiVideoProcessor]:
    return st.session_state.get("multi_proc")


def init_multi_processor(mode: str) -> Optional[MultiVideoProcessor]:
    sources = build_sources(mode)
    if not sources:
        return None
    proc = MultiVideoProcessor()
    if proc.open(sources, mode):
        st.session_state.multi_proc = proc
        st.session_state.cr_dirs = list(sources.keys())
        return proc
    return None


def cleanup_multi_processor():
    proc = get_multi_processor()
    if proc:
        proc.release()
    st.session_state.pop("multi_proc", None)