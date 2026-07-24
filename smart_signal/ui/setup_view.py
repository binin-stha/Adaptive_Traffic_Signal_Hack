"""Setup view — top-down intersection layout for choosing and annotating approaches."""

from typing import List

import cv2
import streamlit as st

from config.constants import DIRECTIONS, DIR_META
from ui.annotation_panel import annotation_panel


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


def _direction_cell(d: str) -> None:
    """Render one road-approach zone in the drone-view grid."""
    meta = DIR_META[d]
    cfg = st.session_state.config[d]
    active = d in _get_active()
    selected = st.session_state.get("annotate_dir") == d

    has_media = cfg["frame"] is not None
    n_shapes = len(cfg["shapes"])
    media_kind = (cfg["media_type"] or "—").upper()

    border = meta["color"] if selected else ("#334155" if active else "#1E293B")
    opacity = "1" if active else "0.35"

    # Status line
    if has_media:
        status = f"{media_kind} · {n_shapes} shape{'s' if n_shapes != 1 else ''}"
        status_color = "#22C55E" if n_shapes > 0 else "#F59E0B"
    else:
        status = "no media"
        status_color = "#64748B"

    st.markdown(
        f"""
        <div style="
            background:#0B1220; border:2px solid {border}; border-radius:12px;
            padding:14px 12px; opacity:{opacity}; position:relative; overflow:hidden;
            transition:border .2s, transform .2s;
        ">
            <!-- dashed lane line decoration -->
            <div style="position:absolute;left:50%;top:0;bottom:0;width:2px;
                background:repeating-linear-gradient(to bottom,#1E293B 0 8px,transparent 8px 16px);
                transform:translateX(-50%);"></div>

            <div style="position:relative;text-align:center;">
                <div style="font-size:26px;color:{meta['color']};line-height:1;">
                    {meta['arrow']}</div>
                <div style="font-size:14px;font-weight:800;letter-spacing:0.12em;
                    color:#F1F5F9;margin:4px 0 2px;">{meta['label']}</div>
                <div style="font-size:10px;color:{status_color};
                    font-family:'JetBrains Mono',monospace;">{status}</div>
                <div style="font-size:9px;color:{'#22C55E' if active else '#64748B'};
                    text-transform:uppercase;letter-spacing:0.1em;margin-top:2px;">
                    {'● active' if active else '○ disabled'}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Thumbnail if a frame exists
    if has_media:
        h, w = cfg["frame"].shape[:2]
        thumb = cv2.resize(cfg["frame"], (int(w * 120 / h), 120))
        st.image(
            cv2.cvtColor(thumb, cv2.COLOR_BGR2RGB),
            use_column_width=True,
        )

    b1, b2 = st.columns(2)
    with b1:
        if st.button(
            "Annotate" if not selected else "● Open",
            key=f"anno_{d}",
            use_container_width=True,
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
    """Render the intersection core."""
    st.markdown(
        """
        <div style="
            height:100%;min-height:220px;background:#0B1220;border:2px solid #1E293B;
            border-radius:12px;display:flex;align-items:center;justify-content:center;
            position:relative;overflow:hidden;
        ">
            <!-- crosswalk stripes -->
            <div style="position:absolute;top:8px;left:50%;transform:translateX(-50%);
                width:70px;height:16px;
                background:repeating-linear-gradient(to right,#334155 0 8px,transparent 8px 16px);"></div>
            <div style="position:absolute;bottom:8px;left:50%;transform:translateX(-50%);
                width:70px;height:16px;
                background:repeating-linear-gradient(to right,#334155 0 8px,transparent 8px 16px);"></div>
            <div style="position:absolute;left:8px;top:50%;transform:translateY(-50%);
                width:16px;height:70px;
                background:repeating-linear-gradient(to bottom,#334155 0 8px,transparent 8px 16px);"></div>
            <div style="position:absolute;right:8px;top:50%;transform:translateY(-50%);
                width:16px;height:70px;
                background:repeating-linear-gradient(to bottom,#334155 0 8px,transparent 8px 16px);"></div>

            <div style="text-align:center;position:relative;">
                <div style="font-size:11px;color:#64748B;text-transform:uppercase;
                    letter-spacing:0.14em;">Intersection</div>
                <div style="font-size:20px;font-weight:800;color:#F1F5F9;
                    letter-spacing:0.06em;margin-top:2px;">CORE</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _corner_cell() -> None:
    st.markdown(
        """
        <div style="height:100%;min-height:60px;background:#080E18;
            border:1px solid #141E2E;border-radius:12px;"></div>
        """,
        unsafe_allow_html=True,
    )


def setup_view() -> None:
    st.markdown(
        """
        <div style="font-size:18px;font-weight:800;color:#F1F5F9;letter-spacing:0.02em;">
            Intersection Setup</div>
        <div style="font-size:11px;color:#64748B;text-transform:uppercase;
            letter-spacing:0.1em;margin-bottom:16px;">
            Top-down layout · enable approaches · click one to annotate</div>
        """,
        unsafe_allow_html=True,
    )

    active = _get_active()
    st.markdown(
        f'<div style="font-size:12px;color:#94A3B8;margin-bottom:12px;">'
        f"Active approaches: <b style='color:#F1F5F9;'>{len(active)}</b> "
        f"({', '.join(d.upper() for d in active) if active else 'none'}) — "
        f"a {len(active)}-way intersection</div>",
        unsafe_allow_html=True,
    )

    # ── Drone-view 3×3 grid ───────────────────────────────────────────────
    r0a, r0b, r0c = st.columns([1, 2, 1])
    r1a, r1b, r1c = st.columns([1, 2, 1])
    r2a, r2b, r2c = st.columns([1, 2, 1])

    with r0a: _corner_cell()
    with r0b: _direction_cell("north")
    with r0c: _corner_cell()

    with r1a: _direction_cell("west")
    with r1b: _center_cell()
    with r1c: _direction_cell("east")

    with r2a: _corner_cell()
    with r2b: _direction_cell("south")
    with r2c: _corner_cell()

    # ── Annotation panel for the selected direction ───────────────────────
    selected = st.session_state.get("annotate_dir")
    if selected:
        st.markdown("---")
        annotation_panel(selected)
    else:
        st.info("Click 'Annotate' on a direction above to draw its lanes and crossings.")