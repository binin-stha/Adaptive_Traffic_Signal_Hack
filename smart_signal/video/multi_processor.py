"""Synchronized multi-direction processing over any frame source.

One `tick` advances every direction's source by one frame and runs the full
pipeline on each: detect → lane-filter → pedestrian wait → shape assignment
→ counting → decision. Works identically for still images, video files, and
live cameras because they all sit behind the FrameSource interface.
"""

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
        """Attach a set of frame sources and prepare for playback."""
        self.sources = dict(sources)
        if not self.sources:
            return False
        self.mode = mode
        self.fps = min(s.fps for s in self.sources.values()) or 30.0
        # total_frames is only meaningful when every source is a finite video
        if all(s.is_finite for s in self.sources.values()):
            self.total_frames = min(s.total_frames for s in self.sources.values())
        else:
            self.total_frames = 0  # image / live run until paused
        return True

    def tick(
        self,
        model,
        conf: float = 0.25,
        imgsz: int = 960,
        speed_thresh: float = SPEED_THRESH_DEFAULT,
        tracker: str = "botsort.yaml",
    ) -> Optional[Dict[str, Any]]:
        """Advance all sources one frame and run the full pipeline.

        Returns a result dict, or None when every source is exhausted.
        """
        # ── read one frame from each source ───────────────────────────────
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

        # ── per-direction pipeline ────────────────────────────────────────
        per_dir: Dict[str, Dict[str, Any]] = {}
        counts_by_dir: Dict[str, Dict[str, Any]] = {}

        for d, frame in frames.items():
            shapes = st.session_state.config[d]["shapes"]

            # 1. detect + track (persistent IDs via the chosen tracker)
            dets = run_tracking(
                frame, model,
                conf=conf, imgsz=imgsz,
                speed_thresh=speed_thresh, tracker=tracker,
            )
            # 2. keep only vehicles inside drawn lanes
            dets = filter_to_lanes(dets, shapes)
            # 3. pedestrian wait-time tracking
            dets = self.ped_wait.update(dets, shapes, dt)
            # 4. assign to lane / crossing / count-line
            track_hist = st.session_state.get("track_history", {})
            dets = assign_to_shapes(dets, shapes, track_hist)
            # 5. count
            counts = counts_for_direction(dets, shapes)

            per_dir[d] = {"dets": dets, "frame": frame, "shapes": shapes}
            counts_by_dir[d] = counts

        # ── decision engine over the aggregated counts ────────────────────
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
        """Release all underlying captures."""
        for src in self.sources.values():
            src.release()
        self.sources = {}


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE BUILDING + SESSION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

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
    """Build sources for the mode and store a ready processor in session."""
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
    """Release the processor and drop it from session state."""
    proc = get_multi_processor()
    if proc:
        proc.release()
    st.session_state.pop("multi_proc", None)