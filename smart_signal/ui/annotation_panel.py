"""Annotation panel — one-click polygon/line drawing via a native Streamlit component."""

import base64
import os
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image

from config.constants import DIRECTIONS, DIR_COLORS, CANVAS_HEIGHT
from visualization.annotate import annotate_frame
from video.multi_processor import cleanup_multi_processor
from models.detector import reset_tracking


def _invalidate_control_room() -> None:
    """Drop cached frames/tracks so the control room rebuilds from fresh media."""
    cleanup_multi_processor()
    reset_tracking()
    st.session_state.pop("last_result", None)
    st.session_state.pop("cr_dirs", None)
    st.session_state.live = False


# ── Register the drawing component ────────────────────────────────────────────
_TOOL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "polygon_tool")
_polygon_tool = components.declare_component("polygon_tool", path=_TOOL_DIR)


def draw_shape_tool(
    image_b64: str, width: int, height: int, mode: str, accent: str, key: str
) -> Optional[Dict[str, Any]]:
    """Render the pen-tool canvas. Returns {'points': [...], 'nonce': n} on save."""
    return _polygon_tool(
        image_b64=image_b64,
        width=width,
        height=height,
        mode=mode,
        accent=accent,
        key=key,
        default=None,
    )


def _frame_to_b64(frame: np.ndarray, disp_w: int, disp_h: int) -> str:
    resized = cv2.resize(frame, (disp_w, disp_h))
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    buf = BytesIO()
    Image.fromarray(rgb).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# ── Vertex editor (adjust saved shapes) ───────────────────────────────────────
def vertex_editor(direction: str, idx: int, shape: Dict[str, Any]) -> None:
    pts = shape["points"]
    with st.expander(f"Edit vertices — {shape['label']} #{idx + 1}", expanded=False):
        new_pts: List[Tuple[float, float]] = []
        for i in range(0, len(pts), 4):
            cols = st.columns(4)
            for j, col in enumerate(cols):
                k = i + j
                if k >= len(pts):
                    break
                with col:
                    x = st.number_input(f"Pt {k+1} X", value=float(pts[k][0]), step=1.0,
                                        key=f"vx_{direction}_{idx}_{k}",
                                        label_visibility="collapsed")
                    y = st.number_input(f"Pt {k+1} Y", value=float(pts[k][1]), step=1.0,
                                        key=f"vy_{direction}_{idx}_{k}",
                                        label_visibility="collapsed")
                    new_pts.append((x, y))

        b1, b2 = st.columns(2)
        with b1:
            if st.button("Apply changes", key=f"applyv_{direction}_{idx}",
                         use_container_width=True):
                st.session_state.config[direction]["shapes"][idx]["points"] = new_pts
                st.rerun()
        with b2:
            if st.button("Delete shape", key=f"delv_{direction}_{idx}",
                         use_container_width=True):
                st.session_state.config[direction]["shapes"].pop(idx)
                st.rerun()


# ── Main panel ────────────────────────────────────────────────────────────────
def annotation_panel(direction: str) -> None:
    cfg = st.session_state.config[direction]
    accent = DIR_COLORS[direction]

    st.markdown(f"### {direction.upper()} approach")
    st.caption("Upload a frame, draw with the pen tool, press Save — the shape is committed instantly.")

    # ── Upload (re-decode only when the file actually changes) ─────────────
    uploaded = st.file_uploader(
        f"Upload image or video — {direction.title()}",
        type=["jpg", "jpeg", "png", "mp4", "mov", "avi"],
        key=f"upload_{direction}",
    )
    if uploaded is not None:
        file_sig = (uploaded.name, uploaded.size)
        sig_key = f"upload_sig_{direction}"
        if st.session_state.get(sig_key) != file_sig:
            st.session_state[sig_key] = file_sig

            is_video = bool(uploaded.type and uploaded.type.startswith("video"))
            cfg["media_type"] = "video" if is_video else "image"

            decoded = None
            if is_video:
                tmp = f"/tmp/ss_{direction}_{uploaded.name}"
                with open(tmp, "wb") as f:
                    f.write(uploaded.getbuffer())
                cap = cv2.VideoCapture(tmp)
                ok, decoded = cap.read()
                cap.release()
                if ok:
                    cfg["media_bytes"] = tmp
            else:
                buf = np.frombuffer(uploaded.getbuffer(), np.uint8)
                decoded = cv2.imdecode(buf, cv2.IMREAD_COLOR)
                if decoded is not None:
                    cfg["media_bytes"] = uploaded.getbuffer()

            if decoded is None:
                st.error("Could not read this file — try a different image or video.")
                cfg["frame"] = None
            else:
                cfg["frame"] = decoded
                _invalidate_control_room()

    # ── Always read the persisted frame and guard before use ───────────────
    frame = cfg.get("frame")
    if frame is None:
        st.info("Upload media to begin drawing.")
        return

    # ── Compute display scale (this block was missing) ─────────────────────
    h, w = frame.shape[:2]
    scale = CANVAS_HEIGHT / h
    cfg["scale"] = scale
    disp_w, disp_h = int(w * scale), CANVAS_HEIGHT

    # ── Tool selection ─────────────────────────────────────────────────────
    draw_choice = st.radio(
        "Annotation tool",
        ["Lane (polygon)", "Zebra crossing (polygon)",
         "Stop line (line — 2 pts)", "Count line (line — 2 pts)"],
        key=f"drawmode_{direction}",
        horizontal=True,
    )
    if "Lane" in draw_choice:
        shape_label, draw_mode = "lane", "polygon"
    elif "Zebra" in draw_choice:
        shape_label, draw_mode = "zebra_crossing", "polygon"
    elif "Stop" in draw_choice:
        shape_label, draw_mode = "stop_line", "line"
    else:
        shape_label, draw_mode = "count_line", "line"

    # ── Lane properties ────────────────────────────────────────────────────
    lane_id = side = travel = None
    is_focus = False
    if shape_label == "lane":
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            lane_id = st.text_input(
                "Lane ID",
                value=f"{direction}_lane_{len([s for s in cfg['shapes'] if s['label']=='lane']) + 1}",
                key=f"laneid_{direction}")
        with c2:
            side = st.selectbox("Side", DIRECTIONS, index=DIRECTIONS.index(direction),
                                key=f"side_{direction}")
        with c3:
            travel = st.selectbox("Travel", ["incoming", "outgoing"],
                                  key=f"travel_{direction}")
        with c4:
            is_focus = st.checkbox("Focus lane", value=True, key=f"focus_{direction}")

    # ── The pen-tool canvas (one-click save) ──────────────────────────────
    image_b64 = _frame_to_b64(frame, disp_w, disp_h)
    result = draw_shape_tool(
        image_b64=image_b64,
        width=disp_w,
        height=disp_h,
        mode=draw_mode,
        accent=accent,
        key=f"tool_{direction}_{shape_label}",
    )

    # Commit the shape exactly once per save (nonce guard)
    if result and isinstance(result, dict) and "points" in result:
        nonce_key = f"tool_nonce_{direction}_{shape_label}"
        if st.session_state.get(nonce_key) != result.get("nonce"):
            st.session_state[nonce_key] = result.get("nonce")
            raw_pts = result["points"]
            min_pts = 2 if draw_mode == "line" else 3
            if len(raw_pts) >= min_pts:
                original_pts = [(p[0] / scale, p[1] / scale) for p in raw_pts]
                entry: Dict[str, Any] = {"label": shape_label, "points": original_pts}
                if shape_label == "lane":
                    entry.update({
                        "id": lane_id or f"{direction}_lane_{len(cfg['shapes']) + 1}",
                        "side": side or direction,
                        "travel": travel or "incoming",
                        "focus": is_focus,
                    })
                cfg["shapes"].append(entry)
                st.success(f"Saved {shape_label} with {len(original_pts)} points.")

    # ── Saved shapes + editor ─────────────────────────────────────────────
    st.markdown("#### Saved shapes")
    if not cfg["shapes"]:
        st.caption("No shapes yet — draw on the image above and press Save.")
    else:
        for i, s in enumerate(cfg["shapes"]):
            if s["label"] == "lane":
                desc = (f"{s.get('id','?')} — {s.get('side','?')}/{s.get('travel','?')}"
                        f"{'  [FOCUS]' if s.get('focus') else ''}")
            elif s["label"] == "zebra_crossing":
                desc = f"Zebra crossing ({len(s['points'])} pts)"
            elif s["label"] == "stop_line":
                desc = "Stop line"
            elif s["label"] == "count_line":
                desc = "Count line"
            else:
                desc = s["label"]
            st.markdown(f"**{i + 1}.** {desc}")
            vertex_editor(direction, i, s)

    # ── Preview overlay ───────────────────────────────────────────────────
    if cfg["shapes"]:
        st.markdown("#### Annotation preview")
        preview = annotate_frame(frame, [], cfg["shapes"])
        st.image(cv2.cvtColor(preview, cv2.COLOR_BGR2RGB),
                 caption=f"{direction.upper()} — all saved annotations",
                 use_column_width=True)