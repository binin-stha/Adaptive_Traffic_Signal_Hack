"""
Session state module for Smart Signal — handles initialization of session state.
"""
from collections import defaultdict, deque
import streamlit as st
from config.constants import DIRECTIONS


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