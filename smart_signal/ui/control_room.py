"""Control Room — real-time MJPEG live tracking dashboard."""

import time

import streamlit as st

from config.constants import DIRECTIONS, DIR_META
from engine.decision_flow import DecisionFlow, MAX_HOLD_TIME, AXIS_LABEL, AXES
from ui.traffic_light import traffic_light_html
from video import live_stream as ls
from video.sources import ImageSource, VideoSource, CameraSource

# Roman Numeral formatting for Art Deco aesthetic
MODE_LABEL = {"image": "STILL IMAGE", "video": "MOTION PICTURE", "live": "LIVE APPARATUS"}
DOCK_HEIGHT = {"2 × 2": 36, "1 × 4": 58, "4 × 1": 18}
MODEL_LABELS = {
    "yolov8n.pt": "YOLOv8n · SWIFT", "yolov8s.pt": "YOLOv8s · BALANCED",
    "yolo11n.pt": "YOLO11n · MODERN SWIFT", "yolo11s.pt": "YOLO11s · MODERN PRECISE",
}
TRACKER_LABELS = {"botsort.yaml": "BoT-SORT · STABLE", "bytetrack.yaml": "ByteTrack · RAPID"}

# ── Design tokens (Art Deco Luxury Palette) ───────
C = {
    "bg":        "#0A0A0A",  # Obsidian Black
    "surface":   "#141414",  # Rich Charcoal
    "border":    "rgba(212, 175, 55, 0.3)",  # Faint Gold
    "border-h":  "#D4AF37",  # Solid Gold
    "text":      "#F2F0E4",  # Champagne Cream
    "text-dim":  "#888888",  # Pewter
    "text-faint": "#5C5C5C", # Darker Pewter
    "gold":      "#D4AF37",  # Metallic Gold
    "gold-light": "#F2E8C4", # Bright Gold
    "ruby":      "#8B0000",  # Deep Red (Stop)
    "emerald":   "#005A36",  # Deep Green (Go)
    "topaz":     "#E67700",  # Amber (Warning)
    "midnight":  "#1E3D59",  # Midnight Blue
}
F_DISPLAY = "'Marcellus', serif"
F_BODY = "'Josefin Sans', sans-serif"


def _inject_dashboard_css() -> None:
    """Art Deco global polish for native widgets."""
    st.markdown(
        f"""
        <style>
          @import url('https://fonts.googleapis.com/css2?family=Josefin+Sans:wght@300;400;600&family=Marcellus&display=swap');

          /* Button Architecture */
          div[data-testid="stButton"] button, .stButton > button {{
              border-radius: 0px !important;
              border: 1px solid {C['border-h']} !important;
              background: transparent !important;
              color: {C['gold']} !important;
              font-family: {F_DISPLAY} !important;
              font-weight: 400 !important;
              letter-spacing: 0.15em !important;
              text-transform: uppercase !important;
              transition: all 0.4s ease;
              min-height: 48px;
          }}
          div[data-testid="stButton"] button:hover {{
              background: {C['gold']} !important;
              color: {C['bg']} !important;
              box-shadow: 0 0 15px rgba(212, 175, 55, 0.4) !important;
              transform: translateY(-2px);
          }}
          div[data-testid="stButton"] button[kind="primary"] {{
              background: rgba(212, 175, 55, 0.1) !important;
              border: 2px solid {C['gold']} !important;
              color: {C['gold-light']} !important;
          }}
          div[data-testid="stButton"] button[kind="primary"]:hover {{
              background: {C['gold']} !important;
              color: {C['bg']} !important;
              box-shadow: 0 0 20px rgba(212, 175, 55, 0.6) !important;
          }}

          /* Typography overrides for widgets */
          div[data-testid="stRadio"] label, div[data-testid="stSelectbox"] label,
          div[data-testid="stSlider"] label, div[data-testid="stNumberInput"] label {{
              font-family: {F_BODY} !important;
              font-size: 12px !important;
              letter-spacing: 0.1em !important;
              text-transform: uppercase !important;
              color: {C['text-dim']} !important;
          }}

          /* Input Fields (Underlines only) */
          .stSelectbox div[data-baseweb="select"], .stNumberInput input {{
              background-color: transparent !important;
              border: none !important;
              border-bottom: 2px solid {C['border-h']} !important;
              border-radius: 0px !important;
              color: {C['text']} !important;
              font-family: {F_BODY} !important;
              box-shadow: none !important;
          }}

          /* Card Hover States */
          .ss-card {{
              background: {C['surface']};
              border: 1px solid {C['border']};
              border-radius: 0px;
              padding: 16px;
              margin-bottom: 16px;
              transition: all 0.4s ease;
              position: relative;
          }}
          .ss-card:hover {{
              border-color: {C['border-h']};
              transform: translateY(-2px);
              box-shadow: 0 5px 20px rgba(212, 175, 55, 0.15);
          }}

          /* Geometric Scrollbar */
          ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
          ::-webkit-scrollbar-track {{ background: {C['bg']}; border-left: 1px solid {C['border']}; }}
          ::-webkit-scrollbar-thumb {{ background: {C['border-h']}; border-radius: 0px; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _live_dock(direction: str, port: int, h_vh: int) -> str:
    meta = DIR_META[direction]
    url = f"http://127.0.0.1:{port}/video?dir={direction}"
    return (
        f'<div class="ss-dock" style="height:{h_vh}vh;position:relative;border-radius:0px;overflow:hidden;'
        f'border:2px solid {C["border-h"]};box-shadow:0 0 10px rgba(212,175,55,0.1);">'
        f'<img src="{url}" style="width:100%;height:100%;object-fit:cover;display:block;filter:grayscale(20%) sepia(10%);"/>'
        f'<div class="ss-osd-top" style="position:absolute;top:0px;left:0px;padding:6px 12px;'
        f'background:rgba(10,10,10,0.85);border-bottom:1px solid {C["border-h"]};border-right:1px solid {C["border-h"]};'
        f'display:flex;align-items:center;gap:8px;">'
        f'<span style="width:8px;height:8px;transform:rotate(45deg);background:{C["gold"]};'
        f'box-shadow:0 0 8px {C["gold"]};"></span>'
        f'<span style="font-family:{F_DISPLAY};font-size:12px;letter-spacing:0.15em;color:{C["gold"]};">'
        f'{meta["arrow"]} {direction.upper()} · LIVE</span></div>'
        f'</div>'
    )


def _idle_dock(direction: str, h_vh: int) -> str:
    meta = DIR_META[direction]
    return (
        f'<div class="ss-dock" style="height:{h_vh}vh;border-radius:0px;'
        f'display:flex;align-items:center;justify-content:center;'
        f'background:repeating-linear-gradient(45deg,{C["surface"]} 0 1px,transparent 1px 10px);'
        f'border:1px dashed {C["border-h"]};">'
        f'<div class="ss-nofeed" style="font-family:{F_DISPLAY};font-size:14px;letter-spacing:0.2em;'
        f'color:{C["gold"]};opacity:0.5;">{meta["arrow"]} {direction.upper()} · AWAITING SIGNAL</div></div>'
    )


def _card_title(label: str) -> str:
    return (
        f'<div class="ss-card-title" style="display:flex;align-items:center;gap:10px;'
        f'font-family:{F_DISPLAY};font-size:14px;font-weight:400;letter-spacing:0.15em;'
        f'text-transform:uppercase;color:{C["gold"]};margin-bottom:12px;border-bottom:1px solid {C["border"]};padding-bottom:6px;">'
        f'<span style="width:6px;height:6px;transform:rotate(45deg);background:{C["gold"]};"></span>{label}</div>'
    )


def _empty(msg: str) -> str:
    """Small placeholder note for empty cards."""
    return (
        f'<div style="font-family:{F_BODY};font-size:11px;color:{C["text-faint"]};'
        f'letter-spacing:0.08em;text-transform:uppercase;padding:6px 0;">{msg}</div>'
    )


def _decision_rail(result) -> str:
    dec = result["decision"] if "decision" in result else result
    axis = dec.get("current_axis")
    held = dec.get("green_held_for", 0.0)
    held_disp = min(held, MAX_HOLD_TIME)
    axis_counts = dec.get("axis_counts", {})
    axis_wait = dec.get("axis_wait", {})
    light = traffic_light_html("green", scale=1.15)
    hold_pct = min(held / MAX_HOLD_TIME, 1.0) * 100
    active = (
        f'<div class="ss-card ss-card-active">{_card_title("Active Phase")}'
        f'<div style="display:flex;align-items:center;gap:16px;">{light}'
        f'<div style="flex:1;">'
        f'<div style="font-family:{F_DISPLAY};font-size:24px;letter-spacing:0.1em;color:{C["gold-light"]};">{AXIS_LABEL.get(axis, "—")}</div>'
        f'<div style="font-family:{F_BODY};font-size:11px;color:{C["text-dim"]};margin-top:4px;letter-spacing:0.1em;text-transform:uppercase;">'
        f'FLOW ENABLED · {held_disp:.0f}s / {MAX_HOLD_TIME}s</div></div></div>'
        f'<div style="margin-top:14px;height:4px;background:{C["bg"]};border-radius:0px;overflow:hidden;'
        f'border:1px solid {C["border"]};"><div style="width:{hold_pct:.0f}%;height:100%;background:{C["gold"]};'
        f'transition:width .3s;"></div></div>'
        f'<div style="margin-top:12px;font-size:11px;color:{C["text-dim"]};font-family:{F_BODY};letter-spacing:0.05em;text-transform:uppercase;">'
        f'<span style="color:{C["gold"]};">{dec.get("last_rule", "")}</span><br/>'
        f'{dec.get("last_reason", "")}</div></div>'
    )

    # ── Crossing protection ─────────
    lock_rows = ""
    for ax in ("NS", "EW"):
        dirs = AXES[ax]
        is_green = ax == dec.get("current_axis")
        arrows = " ".join(DIR_META[d]["arrow"] for d in dirs)
        if is_green:
            state_html = f'<span style="color:{C["gold-light"]};font-family:{F_DISPLAY};font-size:12px;letter-spacing:0.1em;">◆ CLEAR</span>'
            edge = f"border-left:2px solid {C['gold']};"
            dim = ""
        else:
            state_html = f'<span style="color:{C["ruby"]};font-family:{F_DISPLAY};font-size:12px;letter-spacing:0.1em;">◇ HALTED</span>'
            edge = f"border-left:2px solid {C['ruby']};"
            dim = "opacity:.6;"
        lock_rows += (
            f'<div style="display:flex;align-items:center;justify-content:space-between;'
            f'padding:10px 12px;margin:6px 0;background:{C["bg"]};border-radius:0px;{edge}{dim}">'
            f'<span style="font-family:{F_DISPLAY};font-size:14px;letter-spacing:0.1em;color:{C["text"]};">{arrows}&nbsp; {AXIS_LABEL[ax]}</span>'
            f'{state_html}</div>'
        )
    conflict_card = (
        f'<div class="ss-card">{_card_title("Axis Interlock")}'
        f'{lock_rows}'
        f'<div style="font-size:10px;font-family:{F_BODY};color:{C["text-faint"]};margin-top:10px;line-height:1.6;text-transform:uppercase;letter-spacing:0.05em;">'
        f'Strict mechanical exclusivity enforced. Only one axis may proceed simultaneously.</div></div>'
    )

    max_c = max(axis_counts.values()) if axis_counts else 1
    bars = ""
    for ax, c in axis_counts.items():
        pct = int(c / max_c * 100) if max_c else 0
        bars += (
            f'<div style="display:flex;align-items:center;gap:12px;margin:10px 0;">'
            f'<span style="width:30px;font-family:{F_DISPLAY};font-size:14px;color:{C["gold"]};">{ax}</span>'
            f'<div style="flex:1;height:4px;background:{C["bg"]};border:1px solid {C["border"]};">'
            f'<div style="width:{pct}%;height:100%;background:{C["gold"]};transition:width .4s ease-out;"></div></div>'
            f'<span style="width:34px;text-align:right;font-family:{F_BODY};font-size:14px;color:{C["text"]};">{c}</span></div>'
        )
    load_card = f'<div class="ss-card">{_card_title("Volume Tracking")}{bars}</div>'

    wcells = ""
    for ax, w in axis_wait.items():
        alert = w > 90
        b_color = C["gold"] if alert else C["border"]
        t_color = C["gold-light"] if alert else C["text-dim"]
        wcells += (f'<div style="flex:1;text-align:center;padding:12px 6px;background:{C["bg"]};'
                   f'border:1px solid {b_color};"><div style="font-family:{F_DISPLAY};font-size:12px;color:{C["text-faint"]};letter-spacing:0.1em;">{ax}</div>'
                   f'<div style="font-family:{F_BODY};font-size:18px;margin-top:4px;color:{t_color};">{w:.0f}s</div></div>')
    wait_card = (f'<div class="ss-card">{_card_title("Delay Metrics")} <div style="font-family:{F_BODY};font-size:10px;color:{C["text-faint"]};margin-bottom:10px;text-transform:uppercase;letter-spacing:0.1em;">STARVATION THRESHOLD &gt; 90s</div>'
                 f'<div style="display:flex;gap:10px;">{wcells}</div></div>')

    chain = ""
    for step in dec["steps"]:
        name = step["name"]
        if name == "DECISION":
            chain += (f'<div class="ss-chain" style="font-family:{F_BODY};font-size:11px;margin-bottom:6px;border-bottom:1px solid rgba(212,175,55,0.1);padding-bottom:4px;text-transform:uppercase;letter-spacing:0.05em;"><span style="color:{C["text-dim"]};">DECISION →</span> '
                      f'<b style="color:{C["gold-light"]};">{AXIS_LABEL.get(step["detail"]["axis"], "")}</b> '
                      f'· <span style="color:{C["text"]};">{step["detail"]["rule"]}</span></div>')
        elif name == "CONFLICT LOCK":
            chain += (f'<div class="ss-chain" style="font-family:{F_BODY};font-size:11px;margin-bottom:6px;border-bottom:1px solid rgba(212,175,55,0.1);padding-bottom:4px;text-transform:uppercase;letter-spacing:0.05em;"><span style="color:{C["text-dim"]};">INTERLOCK →</span> '
                      f'<b style="color:{C["ruby"]};">{step["detail"]}</b></div>')
        elif step.get("alert") and name in ("CONGESTION", "STARVATION", "PEDESTRIANS"):
            color = {"CONGESTION": C["topaz"], "STARVATION": C["ruby"], "PEDESTRIANS": C["gold"]}[name]
            chain += (f'<div class="ss-chain" style="font-family:{F_BODY};font-size:11px;margin-bottom:6px;border-bottom:1px solid rgba(212,175,55,0.1);padding-bottom:4px;text-transform:uppercase;letter-spacing:0.05em;"><span style="color:{C["text-dim"]};">{name} →</span> '
                      f'<b style="color:{color};">{step["detail"]}</b></div>')
    chain_card = f'<div class="ss-card">{_card_title("Logic Chain")}{chain or _empty("Awaiting directives")}</div>'

    log = ""
    for e in reversed(dec["decision_log"][-6:]):
        log += (f'<div class="ss-log" style="font-family:{F_BODY};font-size:11px;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.05em;"><span style="color:{C["text-faint"]};">[{e["time"]:.0f}s]</span> '
                f'<b style="color:{C["gold"]};">{AXIS_LABEL.get(e["to"], e["to"])}</b> '
                f'<span style="color:{C["text-dim"]};">← {e["rule"]}</span></div>')
    log_card = f'<div class="ss-card">{_card_title("Audit Ledger")}{log or _empty("No entries found")}</div>'

    rules = (f'<div class="ss-card">{_card_title("Operational Mandates")}'
             f'<div style="font-family:{F_BODY};font-size:11px;color:{C["gold"]};text-transform:uppercase;letter-spacing:0.1em;text-align:center;padding:10px;border:1px solid {C["border"]};">LOW ≤ 5 &nbsp;·&nbsp; HIGH ≥ 15<br><br>HOLD {MAX_HOLD_TIME}s &nbsp;·&nbsp; STARVE 90s</div></div>')

    return (f'<div class="ss-rail">{active}{conflict_card}{load_card}{wait_card}'
            f'{chain_card}{log_card}{rules}</div>')


def _get_flow() -> DecisionFlow:
    if "decision_flow" not in st.session_state:
        st.session_state.decision_flow = DecisionFlow()
    return st.session_state.decision_flow


@st.fragment(run_every=0.5)
def decision_panel(dirs):
    """Reads the workers' latest counts, runs the rules, feeds lamps back."""
    with ls.shared.lock:
        counts_by_dir = {d: dict(ls.shared.counts[d]) for d in dirs if d in ls.shared.counts}
    if not counts_by_dir:
        st.markdown(
            f'<div class="ss-card" style="text-align:center;padding:30px 10px;border:1px dashed {C["border-h"]};">'
            f'<div class="ss-idle" style="font-family:{F_DISPLAY};font-size:14px;letter-spacing:0.2em;'
            f'color:{C["gold"]};opacity:0.6;">AWAITING SENSOR INPUT…</div></div>',
            unsafe_allow_html=True,
        )
        return

    now = time.time()
    last = st.session_state.get("_last_decision_t", now)
    dt = max(now - last, 0.05)
    st.session_state._last_decision_t = now

    result = _get_flow().evaluate(counts_by_dir, dt)

    with ls.shared.lock:
        for d, s in result["signal_state"].items():
            ls.shared.signal[d] = s          # workers read this for their lamps

    st.markdown(_decision_rail(result), unsafe_allow_html=True)


def _make_source(direction: str, mode: str):
    cfg = st.session_state.config[direction]
    if mode == "image" and cfg["frame"] is not None:
        return ImageSource(cfg["frame"])
    if mode == "video" and cfg["media_bytes"]:
        return VideoSource(cfg["media_bytes"])
    if mode == "live":
        return CameraSource(st.session_state.get(f"cam_index_{direction}", 0))
    return None


def control_room() -> None:
    _inject_dashboard_css()
    active = st.session_state.get("active_directions", list(DIRECTIONS))

    # Art Deco Header
    st.markdown(
        f'''
        <div style="display:flex;align-items:center;justify-content:space-between;padding:24px 32px;margin-bottom:24px;
                    background:{C["surface"]};border:1px solid {C["border-h"]};position:relative;">
          <div style="position:absolute;top:4px;left:4px;width:12px;height:12px;border-top:1px solid {C["gold"]};border-left:1px solid {C["gold"]};"></div>
          <div style="position:absolute;bottom:4px;left:4px;width:12px;height:12px;border-bottom:1px solid {C["gold"]};border-left:1px solid {C["gold"]};"></div>
          <div style="position:absolute;top:4px;right:4px;width:12px;height:12px;border-top:1px solid {C["gold"]};border-right:1px solid {C["gold"]};"></div>
          <div style="position:absolute;bottom:4px;right:4px;width:12px;height:12px;border-bottom:1px solid {C["gold"]};border-right:1px solid {C["gold"]};"></div>

          <div style="display:flex;align-items:center;gap:20px;">
              <div style="width:16px;height:16px;transform:rotate(45deg);background:transparent;border:2px solid {C["gold"]};
                          box-shadow:0 0 15px {C["gold"]};animation:pulse 2s infinite;flex:none;"></div>
              <div style="font-family:{F_DISPLAY};font-size:28px;color:{C["gold"]};letter-spacing:0.2em;">CONTROL ROOM</div>
          </div>
          <div style="font-family:{F_BODY};font-size:12px;color:{C["text-dim"]};letter-spacing:0.15em;text-transform:uppercase;">
              Operational Command Interface
          </div>
        </div>
        <style>@keyframes pulse{{0%,100%{{opacity:1; box-shadow:0 0 15px {C["gold"]};}}50%{{opacity:.4; box-shadow:0 0 5px {C["gold"]};}}}}</style>
        ''',
        unsafe_allow_html=True,
    )

    # ── detection settings ────────────────────────────────────────────────
    d1, d2, d3, d4 = st.columns(4)
    with d1:
        model_name = st.selectbox("Detection Engine", list(MODEL_LABELS),
                                  format_func=MODEL_LABELS.get, key="model_name")
    with d2:
        tracker_name = st.selectbox("Tracking Protocol", list(TRACKER_LABELS),
                                    format_func=TRACKER_LABELS.get, key="tracker_name")
    with d3:
        det_conf = st.slider("Precision Threshold", 0.10, 0.70, 0.25, 0.05, key="det_conf")
    with d4:
        imgsz = st.selectbox("Resolution Matrix", [416, 640, 960], index=1, key="imgsz")
    current_key = (model_name, tracker_name, imgsz)

    # Art Deco Line Divider
    st.markdown(f'''
        <div style="display:flex;align-items:center;justify-content:center;margin:24px 0;">
            <div style="height:1px;width:100%;background-color:{C["border"]};"></div>
            <div style="width:8px;height:8px;background-color:{C["border-h"]};transform:rotate(45deg);margin:0 15px;flex:none;"></div>
            <div style="height:1px;width:100%;background-color:{C["border"]};"></div>
        </div>
    ''', unsafe_allow_html=True)

    # ── control strip ─────────────────────────────────────────────────────
    cA, cB, cC = st.columns([2, 2, 3])
    with cA:
        mode = st.radio("Signal Origin", ["image", "video", "live"],
                        format_func=lambda m: {"image": "Archival", "video": "Motion", "live": "Live"}[m],
                        horizontal=True, key="cr_mode")
    with cB:
        st.radio("Viewport Matrix", ["2 × 2", "1 × 4", "4 × 1"], horizontal=True, key="feed_layout")
    with cC:
        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button("◆ INITIATE", type="primary", use_container_width=True):
                port = ls.ensure_server()
                st.session_state.mjpeg_port = port
                st.session_state.active_model_key = current_key
                for d in active:
                    src = _make_source(d, mode)
                    if src is not None:
                        shapes = st.session_state.config[d]["shapes"]
                        ls.start_stream(d, src, model_name, tracker_name,
                                        det_conf, imgsz, 3.0, shapes)
                st.session_state.live = True
                st.rerun()
        with b2:
            if st.button("■ SUSPEND", use_container_width=True):
                ls.pause_all()
                st.session_state.live = False
        with b3:
            if st.button("◇ PURGE", use_container_width=True):
                ls.stop_all()
                ls.clear_state()
                st.session_state.pop("decision_flow", None)
                st.session_state.pop("_last_decision_t", None)
                st.session_state.live = False
                st.rerun()

    # ── settings change → clean restart ───────────────────────────────────
    if st.session_state.get("live") and st.session_state.get("active_model_key") != current_key:
        ls.stop_all()
        ls.clear_state()
        st.session_state.pop("decision_flow", None)
        st.session_state.live = False
        st.info("System parameters modified — INITIATE required to bind changes.")

    # ── available sources ─────────────────────────────────────────────────
    if mode == "image":
        avail = [d for d in active if st.session_state.config[d]["media_type"] == "image"
                 and st.session_state.config[d]["frame"] is not None]
    elif mode == "video":
        avail = [d for d in active if st.session_state.config[d]["media_type"] == "video"
                 and st.session_state.config[d]["media_bytes"]]
    else:
        avail = list(active)

    if not avail:
        st.warning(f"No {MODE_LABEL[mode].lower()} signals acquired. Ensure configurations in Setup are complete.")
        return

    if mode == "live":
        cam_cols = st.columns(len(avail))
        for col, d in zip(cam_cols, avail):
            with col:
                st.number_input(f"{d.upper()} OPTIC CHANNEL", 0, 9,
                                value=st.session_state.get(f"cam_index_{d}", 0),
                                key=f"cam_index_{d}")

    st.markdown(f'<div style="height:1px;border-top:2px double {C["border"]};margin:24px 0;"></div>',
                unsafe_allow_html=True)

    # ── live feed grid + decision rail ────────────────────────────────────
    layout = st.session_state.get("feed_layout", "2 × 2")
    h = DOCK_HEIGHT.get(layout, 36)
    port = st.session_state.get("mjpeg_port")

    feed_col, rail_col = st.columns([72, 28], gap="large")
    with feed_col:
        if layout == "2 × 2":
            r1 = st.columns(2, gap="medium")
            r2 = st.columns(2, gap="medium")
            slots = [r1[0], r1[1], r2[0], r2[1]]
        elif layout == "1 × 4":
            slots = st.columns(max(len(avail), 1), gap="medium")
        else:
            slots = [st.columns(1)[0] for _ in avail]
        for i, d in enumerate(avail):
            with slots[i % len(slots)]:
                if port:
                    st.markdown(_live_dock(d, port, h), unsafe_allow_html=True)
                else:
                    st.markdown(_idle_dock(d, h), unsafe_allow_html=True)

    with rail_col:
        decision_panel(avail)