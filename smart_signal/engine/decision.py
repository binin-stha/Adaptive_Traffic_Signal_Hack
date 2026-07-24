"""Rule-based adaptive signal decision engine."""

from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from config.constants import (
    DIRECTIONS,
    WEIGHTS,
    BASE_TIME,
    MIN_GREEN,
    MAX_GREEN,
    MAX_WAIT,
)


# ─────────────────────────────────────────────────────────────────────────────
# GREEN TIME COMPUTATION
# ─────────────────────────────────────────────────────────────────────────────

def compute_green_times(
    counts: Dict[str, Dict[str, Any]],
    wait_times: Dict[str, float],
) -> Tuple[Dict[str, float], str]:
    """Compute per-direction green times from weighted load.

    Returns:
        (green_times_dict, plain_english_reason)
    """
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
        # Zero load → no green needed
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


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL STATE
# ─────────────────────────────────────────────────────────────────────────────

def _get_signal_state() -> Dict[str, str]:
    if "signal_state" not in st.session_state:
        st.session_state.signal_state = {d: "red" for d in DIRECTIONS}
    return st.session_state.signal_state


def set_signal_state(active_direction: Optional[str]) -> None:
    """Set the active direction to green, all others to red."""
    sig = _get_signal_state()
    for d in sig:
        sig[d] = "green" if d == active_direction else "red"


def get_signal_state(direction: str) -> str:
    return _get_signal_state().get(direction, "red")


# ─────────────────────────────────────────────────────────────────────────────
# VIOLATION CHECK
# ─────────────────────────────────────────────────────────────────────────────

def check_violations(
    direction: str,
    dets: List[Dict[str, Any]],
) -> List[int]:
    """Flag pedestrians actively crossing while their signal is green.

    Returns list of offending track IDs.
    """
    if get_signal_state(direction) != "green":
        return []
    return [
        d["track_id"]
        for d in dets
        if d["category"] == "pedestrian"
        and d.get("in_crossing")
        and d["state"] == "moving"
    ]