"""Control Room — docked feeds with per-approach traffic signals and a live decision panel."""

import time

import cv2
import streamlit as st

from config.constants import DIRECTIONS, DIR_META
from models.detector import load_model
from video.multi_processor import (
    get_multi_processor, init_multi_processor, cleanup_multi_processor,
)
from visualization.annotate import annotate_frame
from ui.traffic_light import traffic_light_html, effective_lamp, SIGNAL_COLORS


MODE_LABEL = {"image": "STILL IMAGE", "video": "VIDEO", "live": "LIVE CAMERA"}


# ─────────────────────────────────────────────────────────────────────────────
# HTML BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def _card(title: str, body: str) -> str:
    return (
        f'<div style="background:#0F141C;border:1px solid #1E2733;border-radius:12px;'
        f'padding:14px 16px;margin-bottom:12px;">'
        f'<div style="font-family:IBM Plex Mono,monospace;font-size:10px;letter-spacing:.16em;'
        f'text-transform:uppercase;color:#5C6878;margin-bottom:10px;">{title}</div>'
        f'{body}</div>'
    )


def _dock_header(direction: str, lamp: str, remaining: float, counts: dict) -> str:
    light = traffic_light_html(lamp, scale=0.85)
    color = SIGNAL_COLORS[lamp][0]
    arrow = DIR_META[direction]["arrow"]
    return (
        f'<div style="display:flex;align-items:center;gap:12px;padding:2px 0 10px;">'
        f'{light}'
        f'<div style="flex:1;">'
        f'<div style="font-family:Chakra Petch,sans-serif;font-weight:700;font-size:15px;'
        f'letter-spacing:.14em;color:#E8EDF2;">{arrow} {direction.upper()}</div>'
        f'<div style="font-family:IBM Plex Mono,monospace;font-size:11px;color:#8A97A8;'
        f'margin-top:3px;">{counts["vehicle"]} veh · {counts["pedestrian"]} ped · '
        f'{counts["waiting_pedestrians"]} waiting</div>'
        f'</div>'
        f'<div style="text-align:right;">'
        f'<div style="font-family:IBM Plex Mono,monospace;font-size:22px;font-weight:600;'
        f'color:{color};line-height:1;">{remaining:.0f}<span style="font-size:11px;">s</span></div>'
        f'<div style="font-size:9px;letter-spacing:.14em;color:#5C6878;text-transform:uppercase;'
        f'margin-top:2px;">{lamp}</div>'
        f'</div></div>'
    )


def _decision_panel(result: dict) -> str:
    dec = result["decision"]
    green = dec["current_green"]
    remaining = dec["green_remaining"]
    lamp = effective_lamp("green" if green else "red", remaining if green else None)
    color = SIGNAL_COLORS[lamp][0]
    light = traffic_light_html(lamp, scale=1.5)

    # countdown ring
    frac = min(remaining / 60.0, 1.0)
    circ = 2 * 3.14159 * 26
    offset = circ * (1 - frac)
    ring = (
        f'<svg width="70" height="70" viewBox="0 0 70 70">'
        f'<circle cx="35" cy="35" r="26" fill="none" stroke="#1E2733" stroke-width="6"/>'
        f'<circle cx="35" cy="35" r="26" fill="none" stroke="{color}" stroke-width="6" '
        f'stroke-linecap="round" stroke-dasharray="{circ:.1f}" stroke-dashoffset="{offset:.1f}" '
        f'transform="rotate(-90 35 35)" style="transition:stroke-dashoffset .3s;"/>'
        f'<text x="35" y="40" text-anchor="middle" fill="#E8EDF2" '
        f'font-family="IBM Plex Mono,monospace" font-size="16" font-weight="600">'
        f'{remaining:.0f}</text></svg>'
    )

    active_card = (
        f'<div style="background:linear-gradient(160deg,#0F141C,#0B0F16);'
        f'border:1px solid #1E2733;border-left:4px solid {color};border-radius:12px;'
        f'padding:16px;margin-bottom:12px;display:flex;align-items:center;gap:16px;">'
        f'{light}'
        f'<div style="flex:1;">'
        f'<div style="font-family:IBM Plex Mono,monospace;font-size:10px;letter-spacing:.16em;'
        f'text-transform:uppercase;color:#5C6878;">Active signal</div>'
        f'<div style="font-family:Chakra Petch,sans-serif;font-size:26px;font-weight:700;'
        f'letter-spacing:.08em;color:{color};margin:2px 0;">'
        f'{green.upper() if green else "—"} · {lamp.upper()}</div>'
        f'<div style="font-size:11px;color:#8A97A8;">'
        f'{dec["decision_log"][-1]["reason"] if dec["decision_log"] else "—"}</div>'
        f'</div>{ring}</div>'
    )

    # load bars
    max_load = max(dec["loads"].values()) if dec["loads"] else 1.0
    bars = ""
    for d in DIRECTIONS:
        load = dec["loads"].get(d, 0.0)
        pct = int(load / max_load * 100) if max_load else 0
        c = DIR_META[d]["color"]
        bars += (
            f'<div style="display:flex;align-items:center;gap:10px;margin:6px 0;">'
            f'<span style="width:16px;font-family:Chakra Petch;font-weight:700;font-size:12px;'
            f'color:#8A97A8;">{d[0].upper()}</span>'
            f'<div style="flex:1;height:9px;background:#141B25;border-radius:99px;overflow:hidden;'
            f'border:1px solid #1E2733;">'
            f'<div style="width:{pct}%;height:100%;background:{c};border-radius:99px;'
            f'transition:width .3s;"></div></div>'
            f'<span style="width:40px;text-align:right;font-family:IBM Plex Mono,monospace;'
            f'font-size:11px;color:#CBD5E1;">{load:.1f}</span></div>'
        )
    load_card = _card("Weighted load · veh×1.5 + ped×1.2", bars)

    # wait times
    cells = ""
    for d in DIRECTIONS:
        wt = dec["wait_times"].get(d, 0.0)
        alert = wt > 90
        cells += (
            f'<div style="flex:1;text-align:center;padding:8px 4px;background:#141B25;'
            f'border-radius:9px;{"border:1px solid #FFD60A;" if alert else "border:1px solid #1E2733;"}">'
            f'<div style="font-size:10px;color:#5C6878;">{d[0].upper()}</div>'
            f'<div style="font-family:IBM Plex Mono,monospace;font-size:15px;font-weight:600;'
            f'color:{"#FFD60A" if alert else "#CBD5E1"};">{wt:.0f}s</div></div>'
        )
    wait_card = _card("Red wait times", f'<div style="display:flex;gap:6px;">{cells}</div>')

    # reasoning chain
    lines = ""
    for step in dec["steps"]:
        name = step["name"]
        if name == "DECISION":
            lines += (f'<div style="font-size:12px;color:#8A97A8;padding:3px 0;">'
                      f'<span style="color:#5C6878;">DECISION →</span> '
                      f'<b style="color:#30D158;">{step["detail"]["green"].upper()}</b> '
                      f'{step["detail"]["reason"]}</div>')
        elif name == "STARVATION CHECK" and step.get("alert"):
            a = ", ".join(s.upper() for s in step["alert"])
            lines += (f'<div style="font-size:12px;color:#8A97A8;padding:3px 0;">'
                      f'<span style="color:#5C6878;">STARVATION →</span> '
                      f'<b style="color:#FFD60A;">{a}</b> over threshold</div>')
        elif name == "PEDESTRIAN SAFETY" and step.get("alert"):
            a = ", ".join(s.upper() for s in step["alert"])
            lines += (f'<div style="font-size:12px;color:#8A97A8;padding:3px 0;">'
                      f'<span style="color:#5C6878;">PED SAFETY →</span> '
                      f'<b style="color:#5AC8FA;">crossing at {a}</b></div>')
    chain_card = _card("Reasoning chain", lines or '<div style="color:#5C6878;font-size:12px;">no active constraints</div>')

    # decision log
    log = ""
    for e in reversed(dec["decision_log"][-8:]):
        c = DIR_META.get(e["to"], {}).get("color", "#CBD5E1")
        log += (f'<div style="font-size:11px;padding:4px 0;border-bottom:1px solid #141B25;">'
                f'<span style="font-family:IBM Plex Mono,monospace;color:#5C6878;">'
                f'[{e["time"]:.0f}s]</span> <b style="color:{c};">{e["to"].upper()}</b> '
                f'<span style="color:#8A97A8;">← {e["reason"]}</span></div>')
    log_card = _card("Decision log", log or '<div style="color:#5C6878;font-size:12px;">no decisions yet</div>')

    return active_card + load_card + wait_card + chain_card + log_card


# ─────────────────────────────────────────────────────────────────────────────
# FEED RENDER
# ─────────────────────────────────────────────────────────────────────────────

def _render_feed(direction: str, result: dict) -> None:
    if result is None or direction not in result["per_dir"]:
        st.markdown(
            f'<div style="height:180px;display:flex;align-items:center;justify-content:center;'
            f'color:#3A4655;font-family:IBM Plex Mono,monospace;font-size:12px;'
            f'border:1px dashed #1E2733;border-radius:10px;">'
            f'{DIR_META[direction]["arrow"]} {direction.upper()} — no feed</div>',
            unsafe_allow_html=True,
        )
        return

    pd = result["per_dir"][direction]
    counts = result["counts_by_dir"][direction]
    dec = result["decision"]
    sig = dec["signal_state"].get(direction, "red")
    remaining = dec["green_remaining"] if direction == dec["current_green"] else 0.0
    lamp = effective_lamp(sig, remaining)

    annotated = annotate_frame(pd["frame"], pd["dets"], pd["shapes"])
    # signal lamp burned into the frame corner
    lamp_rgb = {"red": (60, 60, 255), "yellow": (10, 214, 255), "green": (88, 209, 48)}[lamp]
    cv2.circle(annotated, (30, 30), 13, (20, 24, 32), -1)
    cv2.circle(annotated, (30, 30), 9, lamp_rgb, -1)

    for det in pd["dets"]:
        if det["category"] == "pedestrian" and det.get("ped_wait_time", 0) > 1:
            x = int(det["center"][0]) - 30
            y = max(int(det["bbox"][1]) - 24, 14)
            cv2.putText(annotated, f"wait {det['ped_wait_time']}s", (x, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 200, 0), 2)

    st.markdown(_dock_header(direction, lamp, remaining, counts), unsafe_allow_html=True)
    st.image(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB), use_column_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def control_room() -> None:
    active = st.session_state.get("active_directions", list(DIRECTIONS))

    st.markdown(
        '<div style="display:flex;align-items:center;gap:14px;margin-bottom:2px;">'
        '<div style="width:11px;height:11px;border-radius:50%;background:#FF453A;'
        'box-shadow:0 0 12px #FF453A;animation:pulse 1.4s infinite;"></div>'
        '<div style="font-family:Chakra Petch,sans-serif;font-size:24px;font-weight:700;'
        'letter-spacing:.16em;color:#E8EDF2;">CONTROL ROOM</div>'
        '<div style="font-family:IBM Plex Mono,monospace;font-size:11px;color:#5C6878;'
        'letter-spacing:.12em;text-transform:uppercase;">adaptive signal operations</div>'
        '</div><style>@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}</style>',
        unsafe_allow_html=True,
    )

    # ── Mode + layout controls ────────────────────────────────────────────
    mode = st.radio(
        "Source mode", ["image", "video", "live"],
        format_func=lambda m: {"image": "Still Image", "video": "Video", "live": "Live Camera"}[m],
        horizontal=True, key="cr_mode",
    )
    layout = st.radio("Dock layout", ["2 × 2", "1 × 4", "4 × 1"], horizontal=True, key="feed_layout")
    feed_span = st.slider("Feed area width (%)", 50, 80, 66, key="feed_span")

    # available sources for this mode
    if mode == "image":
        avail = [d for d in active if st.session_state.config[d]["media_type"] == "image"
                 and st.session_state.config[d]["frame"] is not None]
    elif mode == "video":
        avail = [d for d in active if st.session_state.config[d]["media_type"] == "video"
                 and st.session_state.config[d]["media_bytes"]]
    else:
        avail = list(active)

    if not avail:
        st.warning(f"No {MODE_LABEL[mode].lower()} sources on active approaches. Upload media in Setup first.")
        return

    if mode == "live":
        cam_cols = st.columns(len(avail))
        for col, d in zip(cam_cols, avail):
            with col:
                st.number_input(f"{d.upper()} cam #", 0, 9,
                                value=st.session_state.get(f"cam_index_{d}", 0),
                                key=f"cam_index_{d}")

    # ── Transport controls ────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 2])
    with c1:
        if st.button("▶ Start", type="primary", use_container_width=True):
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
            st.session_state.pop("last_result", None)
            st.session_state.live = False
            st.rerun()
    with c5:
        batch = st.slider("Frames per update", 1, 12, 4)

    progress = st.progress(0, text="Ready — press Start")

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

    # ── Display (always reads stored result) ──────────────────────────────
    result = st.session_state.get("last_result")
    dirs = st.session_state.get("cr_dirs") or avail

    if result is not None:
        total = result["total_frames"]
        if total > 0:
            pct = result["frame_idx"] / total
            progress.progress(pct, text=(f"{MODE_LABEL[result['mode']]} · frame "
                                         f"{result['frame_idx']}/{total} · {pct*100:.0f}% · "
                                         f"{result['frame_idx']/result['fps']:.1f}s"))
        else:
            progress.progress(1.0, text=(f"{MODE_LABEL[result['mode']]} · tick "
                                         f"{result['frame_idx']} · "
                                         f"{result['frame_idx']/result['fps']:.1f}s simulated"))

    # ── Docked layout ─────────────────────────────────────────────────────
    feed_col, dec_col = st.columns([feed_span, 100 - feed_span], gap="medium")

    with feed_col:
        if layout == "2 × 2":
            rows = [st.columns(2), st.columns(2)]
            slots = [rows[0][0], rows[0][1], rows[1][0], rows[1][1]]
        elif layout == "1 × 4":
            slots = st.columns(len(dirs))
        else:  # 4 × 1
            slots = [st.container() for _ in dirs]

        for i, d in enumerate(dirs):
            with slots[i % len(slots)]:
                with st.container(border=True):
                    _render_feed(d, result)

    with dec_col:
        if result is not None:
            st.markdown(_decision_panel(result), unsafe_allow_html=True)
        else:
            st.markdown(
                '<div style="background:#0F141C;border:1px solid #1E2733;border-radius:12px;'
                'padding:24px;text-align:center;color:#5C6878;'
                'font-family:IBM Plex Mono,monospace;font-size:12px;">'
                'Decision engine idle — press Start</div>',
                unsafe_allow_html=True,
            )

    if proc is not None and proc.finished:
        st.success(f"Video complete — {proc.frame_idx} frames. Press ⟲ Reset to replay.")

    if st.session_state.get("live", False) and proc is not None and not proc.finished:
        time.sleep(0.01)
        st.rerun()