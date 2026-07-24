"""Frame sources — unify still images, video files, and live cameras."""

from typing import Optional, Tuple

import cv2
import numpy as np


class FrameSource:
    """Base class. Subclasses yield one frame per tick."""
    is_finite = False

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        raise NotImplementedError

    def release(self) -> None:
        pass

    @property
    def total_frames(self) -> int:
        return 0

    @property
    def fps(self) -> float:
        return 30.0


class ImageSource(FrameSource):
    """Repeats one still frame forever.

    Feeding the same frame through ByteTrack each tick keeps track IDs
    stable, lets the motion classifier settle on 'waiting', and lets
    wait-times / the starvation guard evolve over simulated time —
    so a single photo still produces a living, changing decision.
    """
    is_finite = False

    def __init__(self, frame: np.ndarray, sim_fps: float = 4.0):
        self._frame = frame
        self._fps = sim_fps

    def read(self):
        return True, self._frame.copy()

    @property
    def fps(self):
        return self._fps


class VideoSource(FrameSource):
    """Successive frames from a video file."""
    is_finite = True

    def __init__(self, path: str):
        self._cap = cv2.VideoCapture(path)
        self._total = (
            int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if self._cap.isOpened() else 0
        )
        self._fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0

    def read(self):
        if not self._cap.isOpened():
            return False, None
        ret, frame = self._cap.read()
        return ret, (frame if ret else None)

    def release(self):
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    @property
    def total_frames(self):
        return self._total

    @property
    def fps(self):
        return self._fps


class CameraSource(FrameSource):
    """Live frames from a webcam / RTSP device."""
    is_finite = False

    def __init__(self, index: int = 0):
        self._cap = cv2.VideoCapture(index)
        self._fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0

    def read(self):
        if not self._cap.isOpened():
            return False, None
        ret, frame = self._cap.read()
        return ret, (frame if ret else None)

    def release(self):
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    @property
    def fps(self):
        return self._fps