"""
UI module for Smart Signal — handles the sidebar rendering.
"""
from datetime import datetime
import streamlit as st
from config.constants import DIRECTIONS, DIR_COLORS


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