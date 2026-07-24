"""Control Room — all active feeds processed in lockstep with a persistent display."""

import time

import cv2
import numpy as np
import streamlit as st

from config.constants import DIRECTIONS, DIR_META
from models.detector import load_model
from video.multi_processor import (
    get_multi_processor, init_multi_processor, cleanup_multi_processor,
)
from visualization.annotate import annotate_frame


def _get_active():
    return st.session_state.get("active_directions", list(DIRECTIONS))


# ─────────────────────────────────────────────────────────────────────────────
# RENDER HELPERS — all read from a result dict, never from the live loop
# ─────────────────────────────────────────────────────────────────────────────

def _render_progress(bar, result):
    if result is None:
        bar.progress(0, text="Ready — press Start")
        return
    total = result["total_frames"] or 1
    pct = result["frame_idx"] / total
    elapsed = result["frame_idx"] / result["fps"]
    bar.progress(
        pct,
        text=(
            f"Frame {result['frame_idx']}/{result['total_frames']} · "
            f"{pct * 100:.0f}% · {elapsed:.1f}s elapsed · "
            f"{result['fps']:.0f} fps source"
        ),
    )


def _render_stats(strip, result):
    if result is None:
        strip.markdown(
            '<div style="padding:10px 16px;background:#0D1420;border:1px solid #1E293B;'
            'border-radius:10px;font-size:12px;color:#64748B;">Awaiting first frame…</div>',
            unsafe_allow_html=True,
        )
        return

    cells = ""
    for d in DIRECTIONS:
        if d not in result["counts_by_dir"]:
            continue
        c = result["counts_by_dir"][d]
        sig = result["decision"]["signal_state"].get(d, "red")
        dot = "#22C55E" if sig == "green" else "#EF4444"
        cells += (
            f'<div style="flex:1;min-width:130px;background:#0D1420;'
            f'border:1px solid #1E293B;border-left:3px solid {DIR_META[d]["color"]};'
            f'border-radius:10px;padding:8px 12px;">'
            f'<div style="display:flex;align-items:center;gap:6px;">'
            f'<span style="font-size:11px;font-weight:800;color:#F1F5F9;">{d.upper()}</span>'
            f'<div style="width:7px;height:7px;border-radius:50%;background:{dot};'
            f'box-shadow:0 0 6px {dot};"></div></div>'
            f'<div style="font-size:11px;color:#94A3B8;margin-top:3px;'
            f'font-family:JetBrains Mono,monospace;">'
            f"veh {c['vehicle']} · ped {c['pedestrian']} · "
            f"wait {c['waiting_pedestrians']}</div></div>"
        )

    strip.markdown(
        f'<div style="display:flex;gap:8px;flex-wrap:wrap;">{cells}</div>',
        unsafe_allow_html=True,
    )


def _render_feeds(slots, result):
    for d, slot in slots.items():
        if result is None or d not in result["per_dir"]:
            slot.markdown(
                f'<div style="height:200px;display:flex;align-items:center;'
                f'justify-content:center;background:#0B1220;border:1px dashed #1E293B;'
                f'border-radius:12px;color:#334155;font-size:12px;">'
                f'{DIR_META[d]["arrow"]} {d.upper()} — no feed</div>',
                unsafe_allow_html=True,
            )
            continue

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

        slot.image(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB), use_column_width=True)


def _render_decision(green_slot, load_slot, wait_slot, chain_slot, log_slot, result):
    if result is None:
        green_slot.markdown(
            '<div style="padding:20px;background:#0D1420;border:1px solid #1E293B;'
            'border-radius:12px;color:#64748B;font-size:12px;text-align:center;">'
            'Decision engine idle</div>',
            unsafe_allow_html=True,
        )
        return

    dec = result["decision"]
    green_dir = dec["current_green"]
    green_color = DIR_META.get(green_dir, {}).get("color", "#64748B")
    remaining = dec["green_remaining"]
    max_load = max(dec["loads"].values()) if dec["loads"] else 1.0

    green_slot.markdown(
        f"""
        <div style="background:#0D1420;border:1px solid #1E293B;
            border-left:4px solid {green_color};border-radius:12px;padding:16px;
            margin-bottom:10px;">
            <div style="font-size:10px;color:#64748B;text-transform:uppercase;
                letter-spacing:0.1em;">Active signal</div>
            <div style="font-size:26px;font-weight:800;color:{green_color};
                letter-spacing:0.05em;margin:4px 0;">
                {green_dir.upper() if green_dir else '—'} · GREEN</div>
            <div style="font-size:15px;color:#F1F5F9;font-family:JetBrains Mono,monospace;">
                {remaining:.1f}s remaining</div>
            <div style="margin-top:8px;height:6px;background:#141E2E;border-radius:99px;
                overflow:hidden;">
                <div style="width:{min(remaining / 60 * 100, 100)}%;height:100%;
                    background:{green_color};border-radius:99px;transition:width .2s;"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    bars = ""
    for d in DIRECTIONS:
        load = dec["loads"].get(d, 0.0)
        pct = int(load / max_load * 100) if max_load > 0 else 0
        bars += (
            f'<div style="display:flex;align-items:center;gap:8px;margin:4px 0;">'
            f'<span style="width:14px;font-size:11px;font-weight:800;color:#94A3B8;">'
            f'{d[0].upper()}</span>'
            f'<div style="flex:1;height:10px;background:#141E2E;border-radius:99px;'
            f'overflow:hidden;border:1px solid #1E293B;">'
            f'<div style="width:{pct}%;height:100%;background:{DIR_META[d]["color"]};'
            f'border-radius:99px;transition:width .2s;"></div></div>'
            f'<span style="width:38px;text-align:right;font-size:11px;'
            f'font-family:JetBrains Mono,monospace;color:#CBD5E1;">{load:.1f}</span></div>'
        )
    load_slot.markdown(
        f'<div style="background:#0D1420;border:1px solid #1E293B;border-radius:12px;'
        f'padding:12px 16px;margin-bottom:10px;">'
        f'<div style="font-size:10px;color:#64748B;text-transform:uppercase;'
        f'letter-spacing:0.1em;margin-bottom:6px;">Weighted load</div>{bars}</div>',
        unsafe_allow_html=True,
    )

    wait_cells = ""
    for d in DIRECTIONS:
        wt = dec["wait_times"].get(d, 0.0)
        alert = wt > 90
        wait_cells += (
            f'<div style="flex:1;text-align:center;padding:6px 4px;background:#141E2E;'
            f'border-radius:8px;{"border:1px solid #F59E0B;" if alert else ""}">'
            f'<div style="font-size:10px;color:#64748B;">{d[0].upper()}</div>'
            f'<div style="font-size:14px;font-weight:800;'
            f'color:{"#F59E0B" if alert else "#CBD5E1"};'
            f'font-family:JetBrains Mono,monospace;">{wt:.0f}s</div></div>'
        )
    wait_slot.markdown(
        f'<div style="background:#0D1420;border:1px solid #1E293B;border-radius:12px;'
        f'padding:12px 16px;margin-bottom:10px;">'
        f'<div style="font-size:10px;color:#64748B;text-transform:uppercase;'
        f'letter-spacing:0.1em;margin-bottom:6px;">Red wait times</div>'
        f'<div style="display:flex;gap:6px;">{wait_cells}</div></div>',
        unsafe_allow_html=True,
    )

    chain = ""
    for step in dec["steps"]:
        name = step["name"]
        if name == "DECISION":
            body = (
                f'<b style="color:#22C55E;">{step["detail"]["green"].upper()}</b> GREEN · '
                f'{step["detail"]["reason"]}'
            )
        elif name == "STARVATION CHECK" and step.get("alert"):
            body = f'<b style="color:#F59E0B;">{", ".join(s.upper() for s in step["alert"])} STARVING</b>'
        elif name == "PEDESTRIAN SAFETY" and step.get("alert"):
            body = f'<b style="color:#38BDF8;">crossing at {", ".join(s.upper() for s in step["alert"])}</b>'
        else:
            continue
        chain += (
            f'<div style="font-size:11px;color:#94A3B8;padding:3px 0;">'
            f'<span style="color:#64748B;">{name}:</span> {body}</div>'
        )
    chain_slot.markdown(
        f'<div style="background:#0D1420;border:1px solid #1E293B;border-radius:12px;'
        f'padding:12px 16px;margin-bottom:10px;">'
        f'<div style="font-size:10px;color:#64748B;text-transform:uppercase;'
        f'letter-spacing:0.1em;margin-bottom:6px;">Reasoning chain</div>'
        f'{chain or "<span style=&quot;font-size:11px;color:#64748B;&quot;>—</span>"}</div>',
        unsafe_allow_html=True,
    )

    log = "".join(
        f'<div style="font-size:11px;padding:3px 0;border-bottom:1px solid #141E2E;">'
        f'<span style="color:#64748B;font-family:JetBrains Mono,monospace;">'
        f'[{e["time"]:.0f}s]</span> '
        f'<b style="color:{DIR_META.get(e["to"], {}).get("color", "#CBD5E1")};">'
        f'{e["to"].upper()}</b> ← {e["reason"]}</div>'
        for e in reversed(dec["decision_log"][-8:])
    )
    log_slot.markdown(
        f'<div style="background:#0D1420;border:1px solid #1E293B;border-radius:12px;'
        f'padding:12px 16px;">'
        f'<div style="font-size:10px;color:#64748B;text-transform:uppercase;'
        f'letter-spacing:0.1em;margin-bottom:6px;">Decision log</div>'
        f'{log or "<span style=&quot;font-size:11px;color:#64748B;&quot;>No decisions yet</span>"}</div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def control_room() -> None:
    active = _get_active()

    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px;">
            <div style="width:10px;height:10px;border-radius:50%;background:#EF4444;
                animation:pulse 1.4s infinite;"></div>
            <div style="font-size:20px;font-weight:800;letter-spacing:0.1em;color:#F1F5F9;">
                CONTROL ROOM</div>
            <div style="font-size:11px;color:#64748B;text-transform:uppercase;
                letter-spacing:0.1em;">{len(active)}-way intersection · live</div>
        </div>
        <style>@keyframes pulse {{0%,100%{{opacity:1}}50%{{opacity:0.3}}}}</style>
        """,
        unsafe_allow_html=True,
    )

    video_paths = {
        d: st.session_state.config[d]["media_bytes"]
        for d in active
        if st.session_state.config[d]["media_type"] == "video"
        and st.session_state.config[d]["media_bytes"]
    }

    if not video_paths:
        st.warning("No videos on active approaches. Upload them in Setup first.")
        return

    st.caption(f"Processing feeds: {', '.join(d.upper() for d in video_paths)}")

    # ── Controls ──────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 2])
    with c1:
        if st.button("▶ Start", use_container_width=True):
            if get_multi_processor() is None:
                init_multi_processor(video_paths)
            st.session_state.live = True
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

    # ── PERSISTENT display skeleton (always rendered, never disappears) ───
    progress = st.empty()
    stats_strip = st.empty()

    feed_col, decision_col = st.columns([7, 5], gap="medium")

    feed_slots = {}
    with feed_col:
        cols = st.columns(2)
        for i, d in enumerate(video_paths):
            with cols[i % 2]:
                st.markdown(
                    f'<div style="padding:4px 8px;border-left:3px solid '
                    f'{DIR_META[d]["color"]};background:#0D1420;'
                    f'border-radius:0 8px 8px 0;margin-bottom:4px;">'
                    f'<span style="font-size:12px;font-weight:800;color:#F1F5F9;">'
                    f'{DIR_META[d]["arrow"]} {d.upper()}</span></div>',
                    unsafe_allow_html=True,
                )
                feed_slots[d] = st.empty()

    with decision_col:
        green_slot = st.empty()
        load_slot = st.empty()
        wait_slot = st.empty()
        chain_slot = st.empty()
        log_slot = st.empty()

    # ── PROCESSING — writes to session_state only ─────────────────────────
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
            st.session_state.last_result = result  # ← the persistence point

        if stepping:
            st.session_state.step_once = False

    # ── DISPLAY — always reads the last stored result ─────────────────────
    result = st.session_state.get("last_result")

    with progress:
        _render_progress(st.progress(0), result)
    _render_stats(stats_strip, result)
    _render_feeds(feed_slots, result)
    _render_decision(green_slot, load_slot, wait_slot, chain_slot, log_slot, result)

    if proc is not None and proc.finished:
        st.success(f"Video complete — {proc.frame_idx} frames processed. Press ⟲ Reset to replay.")

    # Keep the loop going
    if st.session_state.get("live", False) and proc is not None and not proc.finished:
        time.sleep(0.01)
        st.rerun()