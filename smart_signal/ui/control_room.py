"""Control Room — still / video / live feeds with a persistent decision display."""

import time

import cv2
import streamlit as st

from config.constants import DIRECTIONS, DIR_META
from models.detector import load_model
from video.multi_processor import (
    get_multi_processor, init_multi_processor, cleanup_multi_processor,
)
from visualization.annotate import annotate_frame


MODE_LABEL = {"image": "STILL IMAGE", "video": "VIDEO", "live": "LIVE CAMERA"}


# ─────────────────────────────────────────────────────────────────────────────
# RENDER (reads session_state.last_result — never inside the loop)
# ─────────────────────────────────────────────────────────────────────────────

def _render_feed(d: str, result) -> None:
    meta = DIR_META[d]
    st.markdown(f"**{meta['arrow']} {meta['label']}**")

    if result is None or d not in result["per_dir"]:
        st.caption("no feed yet — press Start")
        return

    pd = result["per_dir"][d]
    annotated = annotate_frame(pd["frame"], pd["dets"], pd["shapes"])

    sig = result["decision"]["signal_state"].get(d, "red")
    lamp = (0, 200, 80) if sig == "green" else (60, 60, 255)
    cv2.circle(annotated, (28, 28), 11, lamp, -1)

    for det in pd["dets"]:
        if det["category"] == "pedestrian" and det.get("ped_wait_time", 0) > 1:
            x = int(det["center"][0]) - 30
            y = max(int(det["bbox"][1]) - 24, 14)
            cv2.putText(annotated, f"wait {det['ped_wait_time']}s", (x, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 2)

    st.image(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB), use_column_width=True)
    st.caption(f"signal **{sig.upper()}** · {len(pd['dets'])} detections")


def _render_decision(result) -> None:
    if result is None:
        with st.container(border=True):
            st.markdown("### Decision engine")
            st.caption("idle — press Start")
        return

    dec = result["decision"]
    green = dec["current_green"]
    remaining = dec["green_remaining"]

    # Active signal
    with st.container(border=True):
        st.caption("ACTIVE SIGNAL")
        st.markdown(f"## {green.upper() if green else '—'} · GREEN")
        st.markdown(f"**{remaining:.1f}s** remaining")
        st.progress(min(remaining / 60, 1.0))

    # Weighted load
    with st.container(border=True):
        st.caption("WEIGHTED LOAD  (veh×1.5 + ped×1.2)")
        max_load = max(dec["loads"].values()) if dec["loads"] else 1.0
        for d in DIRECTIONS:
            load = dec["loads"].get(d, 0.0)
            st.caption(f"{d.upper()} — {load:.1f}")
            st.progress(load / max_load if max_load else 0.0)

    # Wait times
    with st.container(border=True):
        st.caption("RED WAIT TIMES")
        wcols = st.columns(len(DIRECTIONS))
        for col, d in zip(wcols, DIRECTIONS):
            with col:
                wt = dec["wait_times"].get(d, 0.0)
                st.metric(d[0].upper(), f"{wt:.0f}s",
                          delta="starving" if wt > 90 else None,
                          delta_color="off")

    # Reasoning chain
    with st.container(border=True):
        st.caption("REASONING CHAIN")
        lines = []
        for step in dec["steps"]:
            name = step["name"]
            if name == "DECISION":
                lines.append(
                    f"- **DECISION** → {step['detail']['green'].upper()} GREEN — "
                    f"{step['detail']['reason']}"
                )
            elif name == "STARVATION CHECK" and step.get("alert"):
                alert = ", ".join(s.upper() for s in step["alert"])
                lines.append(f"- **STARVATION** → {alert} over threshold")
            elif name == "PEDESTRIAN SAFETY" and step.get("alert"):
                alert = ", ".join(s.upper() for s in step["alert"])
                lines.append(f"- **PED SAFETY** → pedestrians crossing at {alert}")
        st.markdown("\n".join(lines) if lines else "- no active constraints")

    # Decision log
    with st.container(border=True):
        st.caption("DECISION LOG")
        if dec["decision_log"]:
            for e in reversed(dec["decision_log"][-8:]):
                st.markdown(
                    f"`[{e['time']:.0f}s]` **{e['to'].upper()}** ← {e['reason']}"
                )
        else:
            st.caption("no decisions yet")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def control_room() -> None:
    active = st.session_state.get("active_directions", list(DIRECTIONS))

    st.markdown("## Control Room")
    st.caption(
        f"{len(active)}-way intersection · choose a source mode and press Start"
    )

    # ── Mode selector ─────────────────────────────────────────────────────
    mode = st.radio(
        "Source mode",
        ["image", "video", "live"],
        format_func=lambda m: {
            "image": "Still Image",
            "video": "Video",
            "live": "Live Camera",
        }[m],
        horizontal=True,
        key="cr_mode",
    )

    # Which directions can serve this mode
    if mode == "image":
        avail = [d for d in active
                 if st.session_state.config[d]["media_type"] == "image"
                 and st.session_state.config[d]["frame"] is not None]
    elif mode == "video":
        avail = [d for d in active
                 if st.session_state.config[d]["media_type"] == "video"
                 and st.session_state.config[d]["media_bytes"]]
    else:
        avail = list(active)

    if not avail:
        st.warning(
            f"No {MODE_LABEL[mode].lower()} sources on active approaches. "
            f"Upload media in Setup first."
        )
        return

    st.caption(f"Sources: {', '.join(d.upper() for d in avail)}")

    # Live mode: camera index per direction
    if mode == "live":
        cam_cols = st.columns(len(avail))
        for col, d in zip(cam_cols, avail):
            with col:
                st.number_input(
                    f"{d.upper()} cam #", min_value=0, max_value=9,
                    value=st.session_state.get(f"cam_index_{d}", 0),
                    key=f"cam_index_{d}",
                )

    # ── Controls ──────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 2])
    with c1:
        if st.button("▶ Start", use_container_width=True):
            proc = get_multi_processor()
            if proc is None or proc.mode != mode:
                cleanup_multi_processor()
                if init_multi_processor(mode) is None:
                    st.error("Could not open sources.")
            st.session_state.live = True
            st.rerun()
    with c2:
        if st.button("⏸ Pause", use_container_width=True):
            st.session_state.live = False
    with c3:
        if st.button("⏭ Step", use_container_width=True):
            st.session_state.live = False
            st.session_state.step_once = True
    with c4:
        if st.button("⟲ Reset", use_container_width=True):
            cleanup_multi_processor()
            st.session_state.last_result = None
            st.session_state.live = False
            st.rerun()
    with c5:
        batch = st.slider("Frames per update", 1, 12, 4)

    # ── Persistent display skeleton ───────────────────────────────────────
    progress = st.progress(0, text="Ready — press Start")
    stats_strip = st.empty()

    feed_col, dec_col = st.columns([7, 5], gap="medium")

    # ── Processing (writes session_state only) ────────────────────────────
    model = load_model()
    proc = get_multi_processor()
    live = st.session_state.get("live", False)
    stepping = st.session_state.get("step_once", False)

    if proc is not None and (live or stepping) and not proc.finished:
        result = None
        for _ in range(batch if live else 1):
            r = proc.tick(model, conf=0.25, imgsz=960, speed_thresh=3.0)
            if r is None:
                st.session_state.live = False
                break
            result = r
        if result is not None:
            st.session_state.last_result = result
        if stepping:
            st.session_state.step_once = False

    # ── Display (always reads the stored result) ──────────────────────────
    result = st.session_state.get("last_result")
    dirs = st.session_state.get("cr_dirs") or avail
    
    if result is not None:
        total = result["total_frames"]
        if total > 0:
            pct = result["frame_idx"] / total
            progress.progress(
                pct,
                text=(f"{MODE_LABEL[result['mode']]} · frame "
                      f"{result['frame_idx']}/{total} · {pct*100:.0f}% · "
                      f"{result['frame_idx']/result['fps']:.1f}s"),
            )
        else:
            progress.progress(
                1.0,
                text=(f"{MODE_LABEL[result['mode']]} · tick "
                      f"{result['frame_idx']} · "
                      f"{result['frame_idx']/result['fps']:.1f}s simulated"),
            )

        # Stats strip
        cells = st.columns(len(result["counts_by_dir"]))
        for col, (d, c) in zip(cells, result["counts_by_dir"].items()):
            with col:
                sig = result["decision"]["signal_state"].get(d, "red")
                st.metric(
                    f"{d.upper()} {'●' if sig == 'green' else '○'}",
                    f"veh {c['vehicle']}",
                    delta=f"ped {c['pedestrian']}",
                    delta_color="off",
                )
    else:
        progress.progress(0, text="Ready — press Start")

    with feed_col:
        fcols = st.columns(2)
        for i, d in enumerate(dirs):
            with fcols[i % 2]:
                _render_feed(d, result)

    with dec_col:
        _render_decision(result)

    if proc is not None and proc.finished:
        st.success(f"Video complete — {proc.frame_idx} frames. Press ⟲ Reset to replay.")

    # Keep the loop alive
    if st.session_state.get("live", False) and proc is not None and not proc.finished:
        time.sleep(0.01)
        st.rerun()