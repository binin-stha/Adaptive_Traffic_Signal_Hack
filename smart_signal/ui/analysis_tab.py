"""Analysis tab — run detection across all directions, compute signal decisions."""

import cv2
import numpy as np
import streamlit as st

from config.constants import DIRECTIONS, DIR_COLORS, SPEED_THRESH_DEFAULT
from models.detector import load_model, run_tracking, reset_tracking
from geometry.assignment import assign_to_shapes, counts_for_direction
from engine.decision import (
    compute_green_times,
    set_signal_state,
    get_signal_state,
    check_violations,
)
from visualization.annotate import annotate_frame


def analysis_tab() -> None:
    st.markdown(
        '<div style="font-size:17px;font-weight:700;color:#F1F5F9;margin-bottom:4px;">'
        "Analysis</div>"
        '<div style="font-size:11px;color:#64748B;text-transform:uppercase;'
        'letter-spacing:0.06em;margin-bottom:16px;">'
        "Run YOLOv8 detection + ByteTrack across all approaches</div>",
        unsafe_allow_html=True,
    )

    # ── Settings ──────────────────────────────────────────────────────────
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        speed_thresh = st.slider(
            "Motion threshold (px/frame)",
            0.5, 15.0, SPEED_THRESH_DEFAULT, 0.5,
            help="Raise if stationary objects flicker between moving/waiting",
        )
    with col_b:
        conf_thresh = st.slider(
            "Detection confidence", 0.1, 0.9, 0.25, 0.05,
        )
    with col_c:
        imgsz = st.selectbox("Inference size", [640, 960, 1280], index=2)

    # ── Reset tracking button ─────────────────────────────────────────────
    if st.button("Reset tracking history", use_container_width=False):
        reset_tracking()
        st.info("Track histories cleared. Next run starts fresh.")

    # ── Run detection ─────────────────────────────────────────────────────
    if st.button(
        "Run detection on all directions",
        type="primary",
        use_container_width=True,
    ):
        # Load model (cached — instant after first load)
        with st.spinner("Loading YOLOv8n (first run downloads ~6 MB)..."):
            model = load_model()

        results_by_dir = {}
        counts_by_dir = {}
        progress = st.progress(0, text="Starting...")

        for idx, direction in enumerate(DIRECTIONS):
            cfg = st.session_state.config[direction]
            if cfg["frame"] is None:
                continue

            progress.progress(
                idx / len(DIRECTIONS),
                text=f"Processing {direction.upper()}...",
            )

            frame = cfg["frame"]

            # 1. Detect + track
            dets = run_tracking(
                frame,
                model,
                conf=conf_thresh,
                imgsz=imgsz,
                speed_thresh=speed_thresh,
            )

            # 2. Assign to drawn shapes
            track_hist = st.session_state.get("track_history", {})
            dets = assign_to_shapes(dets, cfg["shapes"], track_hist)

            # 3. Count
            counts = counts_for_direction(dets, cfg["shapes"])

            # 4. Annotate frame
            annotated = annotate_frame(frame, dets, cfg["shapes"])

            results_by_dir[direction] = {
                "dets": dets,
                "annotated": annotated,
            }
            counts_by_dir[direction] = counts

        progress.progress(1.0, text="Done.")

        if not counts_by_dir:
            st.warning("No directions have uploaded media. Upload images first.")
            return

        # ── Decision engine ───────────────────────────────────────────────
        if "wait_times" not in st.session_state:
            st.session_state.wait_times = {d: 0.0 for d in DIRECTIONS}

        green_times, reason = compute_green_times(
            counts_by_dir, st.session_state.wait_times
        )
        top_dir = max(green_times, key=green_times.get)
        set_signal_state(top_dir if green_times[top_dir] > 0 else None)

        # ── Decision summary ──────────────────────────────────────────────
        st.markdown(
            '<div style="font-size:14px;font-weight:600;color:#94A3B8;'
            'margin:24px 0 8px;">SIGNAL DECISION</div>',
            unsafe_allow_html=True,
        )
        st.success(reason)

        # Green-time cards
        gt_cols = st.columns(len(green_times))
        for col, (d, gt) in zip(gt_cols, green_times.items()):
            with col:
                sig = get_signal_state(d)
                dot = "#22C55E" if sig == "green" else "#EF4444"
                st.markdown(
                    f"""
                    <div style="
                        background:#0D1420; border:1px solid #1E293B;
                        border-top:3px solid {DIR_COLORS[d]};
                        border-radius:12px; padding:16px; text-align:center;
                    ">
                        <div style="font-size:11px;color:#64748B;
                            text-transform:uppercase;letter-spacing:0.06em;">
                            {d.upper()}
                        </div>
                        <div style="font-size:28px;font-weight:700;color:#F1F5F9;
                            font-family:'JetBrains Mono',monospace;margin:6px 0;">
                            {gt:.0f}s
                        </div>
                        <div style="
                            display:inline-flex;align-items:center;gap:5px;
                            padding:2px 10px;border-radius:99px;
                            background:rgba({'34,197,94' if sig=='green' else '239,68,68'},0.12);
                            border:1px solid rgba({'34,197,94' if sig=='green' else '239,68,68'},0.3);
                        ">
                            <div style="width:7px;height:7px;border-radius:50%;
                                background:{dot};box-shadow:0 0 6px {dot};"></div>
                            <span style="font-size:11px;color:{dot};font-weight:600;">
                                {sig.upper()}
                            </span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # ── Per-direction detail ──────────────────────────────────────────
        st.markdown(
            '<div style="font-size:14px;font-weight:600;color:#94A3B8;'
            'margin:24px 0 8px;">PER-APPROACH DETAIL</div>',
            unsafe_allow_html=True,
        )

        detail_cols = st.columns(max(len(results_by_dir), 1))
        for col, (direction, r) in zip(detail_cols, results_by_dir.items()):
            with col:
                st.image(
                    cv2.cvtColor(r["annotated"], cv2.COLOR_BGR2RGB),
                    caption=direction.upper(),
                    use_column_width=True,
                )

                c = counts_by_dir[direction]
                st.markdown(
                    f"""
                    <div style="font-size:12px;color:#CBD5E1;line-height:1.9;">
                        Vehicles: <b>{c['vehicle']}</b>
                        &nbsp;(waiting: {c['waiting_vehicles']})<br/>
                        Pedestrians: <b>{c['pedestrian']}</b>
                        &nbsp;(waiting: {c['waiting_pedestrians']},
                        crossing: {c['crossing_pedestrians']})<br/>
                        Count-line crossings: <b>{c['count_line_crossings']}</b><br/>
                        Total detections: <b>{len(r['dets'])}</b>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Signal state
                sig = get_signal_state(direction)
                dot = "#22C55E" if sig == "green" else "#EF4444"
                st.markdown(
                    f"""
                    <div style="display:inline-flex;align-items:center;gap:6px;
                        padding:4px 12px;border-radius:99px;margin-top:6px;
                        background:rgba({'34,197,94' if sig=='green' else '239,68,68'},0.1);
                        border:1px solid rgba({'34,197,94' if sig=='green' else '239,68,68'},0.3);">
                        <div style="width:8px;height:8px;border-radius:50%;
                            background:{dot};box-shadow:0 0 6px {dot};"></div>
                        <span style="font-size:12px;color:{dot};font-weight:600;">
                            {sig.upper()}
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Violations
                violations = check_violations(direction, r["dets"])
                if violations:
                    st.error(
                        f"VIOLATION — pedestrian(s) {violations} "
                        f"crossing on GREEN at {direction.upper()}"
                    )

        # ── Raw detection table (expandable) ──────────────────────────────
        st.markdown(
            '<div style="font-size:14px;font-weight:600;color:#94A3B8;'
            'margin:24px 0 8px;">RAW DETECTIONS</div>',
            unsafe_allow_html=True,
        )
        for direction, r in results_by_dir.items():
            with st.expander(f"{direction.upper()} — {len(r['dets'])} detections"):
                if not r["dets"]:
                    st.caption("No detections.")
                else:
                    for d in r["dets"]:
                        st.markdown(
                            f'<div style="font-size:11px;color:#94A3B8;'
                            f'font-family:JetBrains Mono,monospace;padding:2px 0;">'
                            f"#{d['track_id']} {d['category']:>10} | "
                            f"{d['class_name']:>10} | "
                            f"conf={d['confidence']:.2f} | "
                            f"state={d['state']:>7} | "
                            f"lane={d.get('lane_id', '—')} | "
                            f"crossing={'YES' if d.get('in_crossing') else 'no'}"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

    # ── Layout save / load ────────────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        '<div style="font-size:14px;font-weight:600;color:#94A3B8;'
        'margin-bottom:8px;">LAYOUT CONFIG</div>',
        unsafe_allow_html=True,
    )

    import json

    export_data = {d: st.session_state.config[d]["shapes"] for d in DIRECTIONS}
    st.download_button(
        "Download layout as JSON",
        json.dumps(export_data, default=str, indent=2),
        file_name="smart_signal_layout.json",
        mime="application/json",
    )

    uploaded_cfg = st.file_uploader(
        "Load a saved layout JSON", type=["json"], key="cfg_upload"
    )
    if uploaded_cfg is not None and st.button("Apply loaded layout"):
        loaded = json.load(uploaded_cfg)
        for d in DIRECTIONS:
            if d in loaded:
                st.session_state.config[d]["shapes"] = loaded[d]
        st.success("Layout applied. Re-upload media per direction.")