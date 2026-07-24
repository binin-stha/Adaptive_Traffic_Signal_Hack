"""Setup view — top-down intersection layout using native Streamlit widgets only."""

from typing import List

import cv2
import streamlit as st

from config.constants import DIRECTIONS, DIR_META
from ui.annotation_panel import annotation_panel


# ─────────────────────────────────────────────────────────────────────────────
# STATE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _get_active() -> List[str]:
    if "active_directions" not in st.session_state:
        st.session_state.active_directions = list(DIRECTIONS)
    return st.session_state.active_directions


def _toggle_direction(d: str) -> None:
    active = _get_active()
    if d in active:
        active.remove(d)
    else:
        active.append(d)
    st.session_state.active_directions = active


def _signal_state(d: str) -> str:
    return st.session_state.get("signal_state", {}).get(d, "red")


# ─────────────────────────────────────────────────────────────────────────────
# CELLS (native widgets — no HTML)
# ─────────────────────────────────────────────────────────────────────────────

def _direction_cell(d: str) -> None:
    """One road approach as a native bordered card."""
    meta = DIR_META[d]
    cfg = st.session_state.config[d]
    active = d in _get_active()
    selected = st.session_state.get("annotate_dir") == d
    sig = _signal_state(d)

    with st.container(border=True):
        # Title
        st.markdown(f"### {meta['arrow']}  {meta['label']}")

        # Media + annotation status
        if cfg["frame"] is not None:
            kind = (cfg["media_type"] or "media").upper()
            n_lanes = len([s for s in cfg["shapes"] if s["label"] == "lane"])
            has_xing = any(s["label"] == "zebra_crossing" for s in cfg["shapes"])
            st.caption(
                f"{kind} uploaded  ·  {n_lanes} lane(s)  ·  "
                f"{'crossing drawn' if has_xing else 'no crossing'}"
            )
        else:
            st.caption("No video — upload to begin")

        # Signal + active state
        st.caption(
            f"Signal: **{sig.upper()}**  ·  "
            f"{'ACTIVE' if active else 'disabled'}"
        )

        # Thumbnail
        if cfg["frame"] is not None:
            h, w = cfg["frame"].shape[:2]
            thumb = cv2.resize(cfg["frame"], (max(int(w * 90 / h), 1), 90))
            st.image(cv2.cvtColor(thumb, cv2.COLOR_BGR2RGB), use_column_width=True)

        # Controls
        b1, b2 = st.columns(2)
        with b1:
            if st.button(
                "● Annotating" if selected else "Annotate",
                key=f"anno_{d}",
                use_container_width=True,
                type="primary" if selected else "secondary",
            ):
                st.session_state.annotate_dir = d
                st.rerun()
        with b2:
            if st.button(
                "Disable" if active else "Enable",
                key=f"act_{d}",
                use_container_width=True,
            ):
                _toggle_direction(d)
                st.rerun()


def _center_cell() -> None:
    """The intersection core."""
    with st.container(border=True):
        st.markdown("### ⬤  JUNCTION")
        st.caption("Signalized intersection core")
        st.caption("Adaptive signal control")
        st.caption("Draw crossings on each approach")


def _corner_cell() -> None:
    """Empty corner spacer."""
    st.markdown(" ")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def setup_view() -> None:
    active = _get_active()

    st.markdown("## Intersection Setup")
    st.caption(
        f"Top-down layout  ·  configured as a **{len(active)}-way intersection**  ·  "
        f"active: {', '.join(d.upper() for d in active) if active else 'none'}"
    )

    # ── Top-down 3×3 grid ─────────────────────────────────────────────────
    r0a, r0b, r0c = st.columns([1, 1.6, 1])
    r1a, r1b, r1c = st.columns([1, 1.6, 1])
    r2a, r2b, r2c = st.columns([1, 1.6, 1])

    with r0a: _corner_cell()
    with r0b: _direction_cell("north")
    with r0c: _corner_cell()

    with r1a: _direction_cell("west")
    with r1b: _center_cell()
    with r1c: _direction_cell("east")

    with r2a: _corner_cell()
    with r2b: _direction_cell("south")
    with r2c: _corner_cell()

    # ── Annotation panel for the selected approach ────────────────────────
    selected = st.session_state.get("annotate_dir")
    if selected:
        st.markdown("---")
        annotation_panel(selected)
    else:
        st.info("Click 'Annotate' on an approach above to draw its lanes, crossing, and lines.")