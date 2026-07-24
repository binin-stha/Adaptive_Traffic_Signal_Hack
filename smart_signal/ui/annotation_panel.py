"""Annotation panel — custom polygon/line pen tool with clipboard save and vertex editing."""

import base64
import json
from io import BytesIO
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image

from config.constants import DIRECTIONS, DIR_COLORS, CANVAS_HEIGHT
from visualization.annotate import annotate_frame


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _frame_to_b64(frame: np.ndarray, disp_w: int, disp_h: int) -> str:
    resized = cv2.resize(frame, (disp_w, disp_h))
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    buf = BytesIO()
    pil.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM DRAWING CANVAS (pure HTML/JS — no external library)
# ─────────────────────────────────────────────────────────────────────────────

def polygon_drawer(
    image_b64: str,
    width: int,
    height: int,
    mode: str,
    accent: str,
    key: str,
) -> None:
    """Render an interactive drawing canvas. Shape data is copied to clipboard."""

    is_line = mode == "line"
    max_points = 2 if is_line else 99
    min_pts = 2 if is_line else 3
    close_label = "Save Line (2 pts)" if is_line else "Close & Save Polygon"

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{
        background:#0D1420;
        font-family:'Inter','Segoe UI',sans-serif;
        display:flex; flex-direction:column; align-items:center; padding:6px;
    }}
    #wrap {{
        position:relative; width:{width}px; height:{height}px;
        border:1px solid #334155; border-radius:10px; overflow:hidden; cursor:crosshair;
    }}
    canvas {{ display:block; }}
    .bar {{
        display:flex; gap:8px; margin-top:10px; flex-wrap:wrap; justify-content:center;
    }}
    .bar button {{
        padding:7px 16px; border-radius:7px; border:1px solid #334155;
        background:#141E2E; color:#F1F5F9; font-size:12px; font-weight:600;
        cursor:pointer; transition:all .15s;
    }}
    .bar button:hover {{ background:#1C2A3E; border-color:{accent}; }}
    .bar button.go {{ background:{accent}; border-color:{accent}; color:#fff; }}
    .bar button.go:hover {{ opacity:.85; }}
    #status {{ color:#94A3B8; font-size:12px; margin-top:6px; text-align:center; }}
    #toast {{
        display:none; position:fixed; top:16px; left:50%; transform:translateX(-50%);
        background:#22C55E; color:#fff; padding:8px 20px; border-radius:8px;
        font-size:13px; font-weight:600; z-index:999;
    }}
</style>
</head>
<body>
<div id="toast">Copied to clipboard</div>
<div id="wrap"><canvas id="c" width="{width}" height="{height}"></canvas></div>
<div class="bar">
    <button class="go" onclick="saveShape()">{close_label}</button>
    <button onclick="undoPoint()">Undo Point</button>
    <button onclick="clearAll()">Clear All</button>
</div>
<div id="status">Click on the image to place vertices</div>

<script>
const cv = document.getElementById('c');
const cx = cv.getContext('2d');
const img = new Image();
let pts = [];
const MAX = {max_points}, MIN = {min_pts}, LINE = {str(is_line).lower()};

img.onload = () => draw();
img.src = "data:image/png;base64,{image_b64}";

cv.addEventListener('click', e => {{
    if (pts.length >= MAX) return;
    const r = cv.getBoundingClientRect();
    const sx = cv.width / r.width, sy = cv.height / r.height;
    pts.push([
        Math.round((e.clientX - r.left) * sx * 10) / 10,
        Math.round((e.clientY - r.top)  * sy * 10) / 10
    ]);
    draw(); stat();
}});

function stat() {{
    const el = document.getElementById('status');
    if (!pts.length) el.textContent = 'Click on the image to place vertices';
    else if (LINE) el.textContent = pts.length + '/2 points — ' + (pts.length >= 2 ? 'click Save Line' : 'click end point');
    else el.textContent = pts.length + ' vertices — add more, then click Save';
}}

function draw() {{
    cx.clearRect(0, 0, cv.width, cv.height);
    cx.drawImage(img, 0, 0, cv.width, cv.height);
    if (!pts.length) return;

    cx.beginPath();
    cx.moveTo(pts[0][0], pts[0][1]);
    for (let i = 1; i < pts.length; i++) cx.lineTo(pts[i][0], pts[i][1]);
    if (!LINE && pts.length >= 3) {{
        cx.closePath();
        cx.fillStyle = 'rgba(255,200,0,.12)';
        cx.fill();
    }}
    cx.strokeStyle = '{accent}'; cx.lineWidth = 2.5; cx.stroke();

    for (let i = 0; i < pts.length; i++) {{
        cx.beginPath();
        cx.arc(pts[i][0], pts[i][1], 6, 0, Math.PI * 2);
        cx.fillStyle = i === 0 ? '#F59E0B' : '{accent}';
        cx.fill();
        cx.strokeStyle = '#fff'; cx.lineWidth = 2; cx.stroke();
        cx.fillStyle = '#fff'; cx.font = 'bold 10px Inter,sans-serif';
        cx.textAlign = 'center';
        cx.fillText(String(i + 1), pts[i][0], pts[i][1] - 10);
    }}
}}

function saveShape() {{
    if (pts.length < MIN) {{
        document.getElementById('status').textContent = 'Need at least ' + MIN + ' points (have ' + pts.length + ')';
        return;
    }}
    const data = JSON.stringify(pts);
    navigator.clipboard.writeText(data).then(() => {{
        const t = document.getElementById('toast');
        t.style.display = 'block';
        setTimeout(() => t.style.display = 'none', 2000);
        document.getElementById('status').textContent = 'Copied! Paste below and click Confirm Save.';
    }}).catch(() => {{
        document.getElementById('status').textContent = 'Copy failed — select and copy manually: ' + data;
    }});
}}

function undoPoint() {{ if (pts.length) {{ pts.pop(); draw(); stat(); }} }}
function clearAll()  {{ pts = []; draw(); stat(); }}
</script>
</body>
</html>"""

    components.html(html, height=height + 90, scrolling=False)


# ─────────────────────────────────────────────────────────────────────────────
# VERTEX EDITOR (adjust saved shapes)
# ─────────────────────────────────────────────────────────────────────────────

def vertex_editor(direction: str, shape_idx: int, shape: Dict[str, Any]) -> None:
    """Show editable vertex coordinates for a saved shape."""
    pts = shape["points"]
    label = shape["label"]

    with st.expander(f"Edit vertices — {label} #{shape_idx + 1}", expanded=False):
        new_pts = []
        cols_per_row = 4
        for i in range(0, len(pts), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, col in enumerate(cols):
                idx = i + j
                if idx >= len(pts):
                    break
                with col:
                    x = st.number_input(
                        f"Pt {idx + 1} X",
                        value=float(pts[idx][0]),
                        step=1.0,
                        key=f"vx_{direction}_{shape_idx}_{idx}",
                        label_visibility="collapsed",
                    )
                    y = st.number_input(
                        f"Pt {idx + 1} Y",
                        value=float(pts[idx][1]),
                        step=1.0,
                        key=f"vy_{direction}_{shape_idx}_{idx}",
                        label_visibility="collapsed",
                    )
                    new_pts.append((x, y))

        if st.button("Apply vertex changes", key=f"applyv_{direction}_{shape_idx}"):
            st.session_state.config[direction]["shapes"][shape_idx]["points"] = new_pts
            st.rerun()

        if st.button("Delete this shape", key=f"delv_{direction}_{shape_idx}"):
            st.session_state.config[direction]["shapes"].pop(shape_idx)
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PANEL
# ─────────────────────────────────────────────────────────────────────────────

def annotation_panel(direction: str) -> None:
    cfg = st.session_state.config[direction]
    accent = DIR_COLORS[direction]

    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
            <div style="width:4px;height:28px;border-radius:4px;background:{accent};"></div>
            <div>
                <div style="font-size:17px;font-weight:700;color:#F1F5F9;">
                    {direction.upper()} APPROACH
                </div>
                <div style="font-size:11px;color:#64748B;text-transform:uppercase;letter-spacing:0.06em;">
                    Upload frame → click vertices → save → adjust
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Upload ────────────────────────────────────────────────────────────
    uploaded = st.file_uploader(
        f"Upload image or video — {direction.title()}",
        type=["jpg", "jpeg", "png", "mp4", "mov", "avi"],
        key=f"upload_{direction}",
    )

    if uploaded is not None:
        is_video = uploaded.type and uploaded.type.startswith("video")
        cfg["media_type"] = "video" if is_video else "image"
        if is_video:
            tmp = f"/tmp/ss_{direction}_{uploaded.name}"
            with open(tmp, "wb") as f:
                f.write(uploaded.getbuffer())
            cap = cv2.VideoCapture(tmp)
            ok, frame = cap.read()
            cap.release()
            if not ok:
                st.error("Could not read the first frame.")
                return
            cfg["media_bytes"] = tmp
        else:
            buf = np.frombuffer(uploaded.getbuffer(), np.uint8)
            frame = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            if frame is None:
                st.error("Could not decode this image.")
                return
            cfg["media_bytes"] = uploaded.getbuffer()
        cfg["frame"] = frame

    if cfg["frame"] is None:
        st.info("Upload media to begin drawing.")
        return

    frame = cfg["frame"]
    h, w = frame.shape[:2]
    scale = CANVAS_HEIGHT / h
    cfg["scale"] = scale
    disp_w = int(w * scale)
    disp_h = CANVAS_HEIGHT

    # ── Tool selection ────────────────────────────────────────────────────
    draw_choice = st.radio(
        "Annotation tool",
        [
            "Lane (polygon)",
            "Zebra crossing (polygon)",
            "Stop line (line — 2 pts)",
            "Count line (line — 2 pts)",
        ],
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

    # ── Lane properties ───────────────────────────────────────────────────
    lane_id = side = travel = None
    is_focus = False
    if shape_label == "lane":
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            lane_id = st.text_input(
                "Lane ID",
                value=f"{direction}_lane_{len([s for s in cfg['shapes'] if s['label'] == 'lane']) + 1}",
                key=f"laneid_{direction}",
            )
        with c2:
            side = st.selectbox("Side", DIRECTIONS,
                                index=DIRECTIONS.index(direction),
                                key=f"side_{direction}")
        with c3:
            travel = st.selectbox("Travel", ["incoming", "outgoing"],
                                  key=f"travel_{direction}")
        with c4:
            is_focus = st.checkbox("Focus lane", value=True,
                                   key=f"focus_{direction}")

    # ── Drawing canvas ────────────────────────────────────────────────────
    image_b64 = _frame_to_b64(frame, disp_w, disp_h)
    polygon_drawer(
        image_b64=image_b64,
        width=disp_w,
        height=disp_h,
        mode=draw_mode,
        accent=accent,
        key=f"{direction}_{shape_label}",
    )

    # ── Paste + Confirm Save ──────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:12px;font-weight:600;color:#94A3B8;margin:12px 0 4px;">'
        "PASTE SHAPE DATA (auto-copied from canvas Save button)</div>",
        unsafe_allow_html=True,
    )
    pasted = st.text_area(
        "Shape JSON",
        key=f"paste_{direction}_{shape_label}",
        placeholder='Click "Close & Save" on the canvas above, then paste here (Ctrl+V)',
        height=68,
    )

    if st.button("Confirm Save Shape", key=f"confirm_{direction}", use_container_width=True):
        if not pasted.strip():
            st.warning("Paste the shape JSON from the canvas first.")
        else:
            try:
                raw_pts = json.loads(pasted)
                if not isinstance(raw_pts, list) or len(raw_pts) < (2 if draw_mode == "line" else 3):
                    st.error("Not enough points in the pasted data.")
                else:
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
                    st.rerun()
            except json.JSONDecodeError:
                st.error("Invalid JSON. Make sure you copied the full shape data.")

    # ── Saved shapes + vertex editor ──────────────────────────────────────
    st.markdown(
        '<div style="font-size:13px;font-weight:600;color:#94A3B8;margin:20px 0 8px;">'
        "SAVED SHAPES (expand to edit vertices)</div>",
        unsafe_allow_html=True,
    )

    if not cfg["shapes"]:
        st.caption("No shapes saved yet.")
    else:
        for i, s in enumerate(cfg["shapes"]):
            if s["label"] == "lane":
                desc = (
                    f"{s.get('id','?')} — {s.get('side','?')}/{s.get('travel','?')}"
                    f"{'  [FOCUS]' if s.get('focus') else ''}"
                )
            elif s["label"] == "zebra_crossing":
                desc = f"Zebra crossing ({len(s['points'])} pts)"
            elif s["label"] == "stop_line":
                desc = "Stop line"
            elif s["label"] == "count_line":
                desc = "Count line"
            else:
                desc = s["label"]

            st.markdown(
                f'<div style="font-size:12px;color:#CBD5E1;padding:2px 0;">'
                f"{i + 1}. {desc}</div>",
                unsafe_allow_html=True,
            )
            vertex_editor(direction, i, s)

    # ── Preview ───────────────────────────────────────────────────────────
    if cfg["shapes"]:
        st.markdown(
            '<div style="font-size:13px;font-weight:600;color:#94A3B8;margin:16px 0 8px;">'
            "ANNOTATION PREVIEW</div>",
            unsafe_allow_html=True,
        )
        preview = annotate_frame(frame, [], cfg["shapes"])
        st.image(
            cv2.cvtColor(preview, cv2.COLOR_BGR2RGB),
            caption=f"{direction.upper()} — all saved annotations",
            use_column_width=True,
        )