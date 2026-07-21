"""
PCBVisor — Streamlit Application
Main entry point: streamlit run app.py
"""

import base64
import sys
from pathlib import Path

import cv2
import numpy as np
import streamlit as st

# Ensure processing/ and core/ are importable from scripts/
sys.path.insert(0, str(Path(__file__).parent))

from core.pipeline import PipelineParams, PipelineRunner, PipelineState

# ─── Page Config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="PCBVisor",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Step progress rows */
.step-row {
    display: flex;
    align-items: center;
    padding: 5px 8px;
    border-radius: 6px;
    margin-bottom: 2px;
    font-size: 0.83rem;
    font-family: 'JetBrains Mono', monospace;
    transition: background 0.15s;
}
.step-row:hover { background: rgba(255,255,255,0.04); }
.step-row .icon { width: 22px; flex-shrink: 0; }
.step-row .label { flex: 1; color: #c8d6e0; }
.step-row .dur { color: #4ecdc4; font-size: 0.78rem; min-width: 60px; text-align: right; }
.step-row.failed .label { color: #ff6b6b; }
.step-row.pending .label { color: #555; }

/* Metric cards */
.metric-card {
    background: linear-gradient(135deg, #1a1f2e, #232b3e);
    border: 1px solid #2d3a4f;
    border-radius: 10px;
    padding: 14px 18px;
    text-align: center;
}
.metric-card .mval {
    font-size: 1.7rem;
    font-weight: 700;
    color: #00d4ff;
    font-family: 'JetBrains Mono', monospace;
}
.metric-card .mlabel {
    font-size: 0.72rem;
    color: #6b7fa3;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 2px;
}

/* Section headers */
.section-title {
    font-size: 0.72rem;
    color: #4a6080;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    font-weight: 600;
    margin: 16px 0 8px 0;
    border-bottom: 1px solid #1e2a3a;
    padding-bottom: 5px;
}

/* Log line styling */
.log-info    { color: #8ab4c8; }
.log-warning { color: #f0c040; }
.log-error   { color: #ff6b6b; }
.log-debug   { color: #6b7fa3; }

/* Only hide the Deploy button, keep everything else */
[data-testid="stDeployButton"] {
    display: none !important;
}
</style>
""", unsafe_allow_html=True)

# ─── Session State Init ───────────────────────────────────────────────────────

if "pipeline_state" not in st.session_state:
    st.session_state.pipeline_state = None
if "last_hash" not in st.session_state:
    st.session_state.last_hash = None
if "selected_step_id" not in st.session_state:
    st.session_state.selected_step_id = None
if "last_png_name" not in st.session_state:
    st.session_state.last_png_name = None
if "last_csv_name" not in st.session_state:
    st.session_state.last_csv_name = None

# ─── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
<div style="
    background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
    border-radius: 8px;
    padding: 8px 12px;
    margin-bottom: 12px;
    text-align: center;
">
    <span style="font-size: 1.5rem; font-weight: 700;
         background: linear-gradient(90deg, #00d4ff, #7b2ff7);
         -webkit-background-clip: text; -webkit-text-fill-color: transparent;
         letter-spacing: 1px;">🔬 PCBVisor</span>
    <div style="font-size: 0.9rem; color: #FFFFFF; margin-top: 1px;">
        PCB Fiducial Detection Pipeline v1.00
    </div>
</div>
""", unsafe_allow_html=True)
    st.markdown('<div class="section-title">📁 Inputs</div>', unsafe_allow_html=True)
    png_file = st.file_uploader("PCB Image (.png)", type=["png"], key="png_upload")
    csv_file = st.file_uploader("Fiducial CSV (PPL)", type=["csv"], key="csv_upload")
    run_top_clicked = st.button("▶ Run", use_container_width=True, type="primary", key="run_top")

    st.markdown('<div class="section-title">⚙ Image Expansion</div>', unsafe_allow_html=True)
    padding = st.slider("Padding (px)", 0, 300, 125, 5, key="padding")
    transparent_color = st.color_picker("Transparent color key", "#FEFEFE", key="trans_color")
    trans_tol = st.slider("Color key tolerance", 0, 10, 0, 1, key="trans_tol")

    def _hex_to_rgb(h: str) -> tuple[int, int, int]:
        h = h.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    tr, tg, tb = _hex_to_rgb(transparent_color)

    st.markdown('<div class="section-title">⚙ Edge Detection</div>', unsafe_allow_html=True)
    edge_method = st.selectbox("Method", ["binary", "canny"],
                                format_func=lambda x: "Canny" if x == "canny" else "Binary (B&W)",
                                key="edge_method")
    if edge_method == "canny":
        canny_thr = st.slider("Canny upper threshold", 10, 500, 100, 5, key="canny_thr")
        bin_thr = 127
        bin_inv = False
    else:
        canny_thr = 100.0
        bin_thr = st.slider("Binary threshold", 0, 255, 127, 1, key="bin_thr")
        bin_inv = st.toggle("Invert", value=False, key="bin_inv")

    st.markdown('<div class="section-title">⚙ Detection Filters</div>', unsafe_allow_html=True)
    min_circ = st.slider("Min circularity", 0.50, 1.00, 0.75, 0.01, key="min_circ")
    min_rad = st.slider("Min radius (px)", 1, 100, 6, 1, key="min_rad")
    max_rad = st.slider("Max radius (px)", 1, 200, 18, 1, key="max_rad")
    proximity_tol = st.slider("Proximity tolerance (px)", 10, 200, 64, 2, key="prox_tol")

    st.markdown('<div class="section-title">⚙ Origin Finder</div>', unsafe_allow_html=True)
    layer_options = ["auto", "TopLayer", "BottomLayer", "TOP", "BOT"]
    layer = st.selectbox("Layer", layer_options, key="layer")
    ratio_tol = st.slider("Ratio tolerance", 0.1, 5.0, 1.0, 0.1,
                           format="%.1f", key="ratio_tol")

    st.markdown('<div class="section-title">⚙ Display</div>', unsafe_allow_html=True)
    marker_shape = st.selectbox("Marker shape", ["reticle", "circle", "concentric", "target"],
                                 key="marker_shape")
    line_thick = st.slider("Line thickness", 1, 8, 3, 1, key="line_thick")
    fid_color = st.color_picker("Fiducial color", "#00FF00", key="fid_color")
    orig_color = st.color_picker("Origin color", "#FFFFFF", key="orig_color")
    size_mult = st.slider("Marker size multiplier", 1.0, 6.0, 3.0, 0.1, key="size_mult")
    rad_offset = st.slider("Fiducial radius offset (px)", 0, 40, 10, 1, key="rad_offset")
    show_labels = st.toggle("Show labels", value=True, key="show_labels")
    show_coords = st.toggle("Show coordinates (mm)", value=False, key="show_coords")
    orig_size = st.slider("Origin marker size (px)", 10, 100, 40, 2, key="orig_size")

    st.markdown("---")
    col_auto, col_run = st.columns([1, 1])
    with col_auto:
        autorun = st.toggle("🔄 Autorun", value=False, key="autorun")
    with col_run:
        run_bottom_clicked = st.button("▶ Run", use_container_width=True, type="primary", key="run_bottom")

# ─── Detect File Changes ──────────────────────────────────────────────────────

# If a new PNG or CSV file was uploaded, reset the pipeline state so the
# preview is shown instead of stale results.
if png_file is not None and png_file.name != st.session_state.last_png_name:
    st.session_state.pipeline_state = None
if csv_file is not None and csv_file.name != st.session_state.last_csv_name:
    st.session_state.pipeline_state = None

# ─── Build Params ─────────────────────────────────────────────────────────────

params = PipelineParams(
    padding=padding,
    transparent_r=tr, transparent_g=tg, transparent_b=tb,
    transparent_tolerance=trans_tol,
    edge_method=edge_method,
    canny_threshold=float(canny_thr),
    binary_threshold=bin_thr,
    binary_invert=bin_inv,
    min_circularity=min_circ,
    min_radius=min_rad,
    max_radius=max_rad,
    proximity_tolerance=proximity_tol,
    layer=layer,
    ratio_tolerance=ratio_tol,
    marker_shape=marker_shape,
    line_thickness=line_thick,
    fiducial_color_hex=fid_color,
    marker_size_multiplier=size_mult,
    fiducial_radius_offset=rad_offset,
    show_labels=show_labels,
    show_coordinates=show_coords,
    origin_marker_size=orig_size,
    origin_color_hex=orig_color,
)
current_hash = params.hash()

# ─── Pipeline Execution ────────────────────────────────────────────────────────

should_run = (run_top_clicked or run_bottom_clicked) or (
    autorun
    and png_file is not None
    and csv_file is not None
    and (
        current_hash != st.session_state.last_hash
        or png_file.name != st.session_state.last_png_name
        or csv_file.name != st.session_state.last_csv_name
    )
)

if should_run and png_file and csv_file:
    runner = PipelineRunner()
    with st.spinner("Running PCBVisor pipeline…"):
        state: PipelineState = runner.run(
            image_bytes=png_file.getvalue(),
            image_filename=png_file.name,
            csv_bytes=csv_file.getvalue(),
            csv_filename=csv_file.name,
            params=params,
        )
    st.session_state.pipeline_state = state
    st.session_state.last_hash = current_hash
    st.session_state.last_png_name = png_file.name
    st.session_state.last_csv_name = csv_file.name

    # Default step to display = last step with image
    steps_with_img = state.steps_with_images()
    if steps_with_img:
        st.session_state.selected_step_id = steps_with_img[-1].step_id

elif should_run and (not png_file or not csv_file):
    st.warning("⚠ Please upload both a PNG image and a CSV file before running.")

def render_canvas_html(img_w: int, img_h: int, b64: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
<style>
  body {{
    margin: 0;
    padding: 0;
    background: #0e1117;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    align-items: center;
  }}
  #controls {{
    width: 100%;
    padding: 6px 14px;
    background: #1a1f2e;
    display: flex;
    align-items: center;
    gap: 12px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: #6b9fcf;
    box-sizing: border-box;
  }}
  #zoom-label {{ color: #4ecdc4; font-weight: 600; min-width: 55px; }}
  #zoom-slider {{ flex: 1; accent-color: #00d4ff; }}
  .ctrl-btn {{
    background: #2d3a4f;
    color: #c8d6e0;
    border: none;
    padding: 4px 14px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-family: inherit;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    transition: background 0.15s;
  }}
  .ctrl-btn:hover {{ background: #3a4a60; }}
  canvas {{
    cursor: grab;
    display: block;
  }}
  canvas:active {{ cursor: grabbing; }}
</style>
</head>
<body>
<div id="controls">
  <span>Zoom:</span>
  <input id="zoom-slider" type="range" min="10" max="800" value="100" step="5">
  <span id="zoom-label">100%</span>
  <button id="reset-btn" class="ctrl-btn" onclick="resetView()">Fit</button>
  <button id="fullscreen-btn" class="ctrl-btn" onclick="toggleFullscreen()">⛶ Fullscreen</button>
  <span style="margin-left:auto;color:#3d5068;">Scroll=zoom · Drag=pan · DblClick=fit</span>
</div>
<canvas id="c"></canvas>

<script>
const IMG_W = {img_w};
const IMG_H = {img_h};
const src = "data:image/png;base64,{b64}";

const img = new Image();
img.src = src;

const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');
const slider = document.getElementById('zoom-slider');
const zLabel = document.getElementById('zoom-label');
const fsBtn = document.getElementById('fullscreen-btn');

let scale = 1.0;
let ox = 0, oy = 0;
let dragging = false;
let lastX = 0, lastY = 0;

function isFullscreen() {{
  return !!(document.fullscreenElement || document.webkitFullscreenElement);
}}

function toggleFullscreen() {{
  if (!isFullscreen()) {{
    const el = document.documentElement;
    if (el.requestFullscreen) {{
      el.requestFullscreen();
    }} else if (el.webkitRequestFullscreen) {{
      el.webkitRequestFullscreen();
    }}
  }} else {{
    if (document.exitFullscreen) {{
      document.exitFullscreen();
    }} else if (document.webkitExitFullscreen) {{
      document.webkitExitFullscreen();
    }}
  }}
}}

function updateFullscreenBtn() {{
  if (isFullscreen()) {{
    fsBtn.innerHTML = '🗗 Exit Fullscreen';
    fsBtn.style.background = '#00d4ff';
    fsBtn.style.color = '#0e1117';
  }} else {{
    fsBtn.innerHTML = '⛶ Fullscreen';
    fsBtn.style.background = '#2d3a4f';
    fsBtn.style.color = '#c8d6e0';
  }}
}}

['fullscreenchange', 'webkitfullscreenchange'].forEach(evt => {{
  document.addEventListener(evt, () => {{
    updateFullscreenBtn();
    resetView();
  }});
}});

function getCanvasSize() {{
  const avail = window.innerWidth;
  const ctrlH = document.getElementById('controls') ? document.getElementById('controls').offsetHeight : 35;
  const h = isFullscreen() ? (window.innerHeight - ctrlH) : 650;
  return [avail, h];
}}

function fitScale() {{
  const [cw, ch] = getCanvasSize();
  return Math.min(cw / IMG_W, ch / IMG_H, 1.0);
}}

function resetView() {{
  const [cw, ch] = getCanvasSize();
  scale = fitScale();
  ox = (cw - IMG_W * scale) / 2;
  oy = (ch - IMG_H * scale) / 2;
  slider.value = Math.round(scale * 100);
  zLabel.textContent = Math.round(scale * 100) + '%';
  draw();
}}

function draw() {{
  const [cw, ch] = getCanvasSize();
  canvas.width = cw;
  canvas.height = ch;
  ctx.clearRect(0, 0, cw, ch);
  ctx.fillStyle = '#0e1117';
  ctx.fillRect(0, 0, cw, ch);
  ctx.drawImage(img, ox, oy, IMG_W * scale, IMG_H * scale);
}}

img.onload = () => resetView();

canvas.addEventListener('wheel', (e) => {{
  e.preventDefault();
  const rect = canvas.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  const my = e.clientY - rect.top;

  const delta = e.deltaY < 0 ? 1.1 : 0.9;
  const newScale = Math.min(8.0, Math.max(0.1, scale * delta));

  ox = mx - (mx - ox) * (newScale / scale);
  oy = my - (my - oy) * (newScale / scale);
  scale = newScale;

  slider.value = Math.round(scale * 100);
  zLabel.textContent = Math.round(scale * 100) + '%';
  draw();
}}, {{ passive: false }});

canvas.addEventListener('mousedown', (e) => {{
  dragging = true;
  lastX = e.clientX;
  lastY = e.clientY;
}});
window.addEventListener('mousemove', (e) => {{
  if (!dragging) return;
  ox += e.clientX - lastX;
  oy += e.clientY - lastY;
  lastX = e.clientX;
  lastY = e.clientY;
  draw();
}});
window.addEventListener('mouseup', () => dragging = false);

canvas.addEventListener('dblclick', () => resetView());

slider.addEventListener('input', () => {{
  const [cw, ch] = getCanvasSize();
  const newScale = parseInt(slider.value) / 100;
  ox = cw / 2 - (cw / 2 - ox) * (newScale / scale);
  oy = ch / 2 - (ch / 2 - oy) * (newScale / scale);
  scale = newScale;
  zLabel.textContent = Math.round(scale * 100) + '%';
  draw();
}});

window.addEventListener('resize', () => resetView());
</script>
</body>
</html>
"""

# ─── Main Panel ────────────────────────────────────────────────────────────────

state: PipelineState = st.session_state.pipeline_state

tab1, tab2 = st.tabs(["🖼 Image Viewer & Statistics", "📋 Pipeline Steps & Execution Logs"])

# ── TAB 1: Image Viewer & Statistics ─────────────────────────────────────────
with tab1:
    if state is not None and state.steps_with_images():
        steps_with_img = state.steps_with_images()

        # Step selector combobox
        step_options = {s.step_id: f"{s.step_id:02d}. {s.step_label}" for s in steps_with_img}
        selected_id = st.session_state.selected_step_id

        if selected_id not in step_options:
            selected_id = steps_with_img[-1].step_id

        selected_label = st.selectbox(
            "Show step output:",
            options=list(step_options.keys()),
            format_func=lambda x: step_options[x],
            index=list(step_options.keys()).index(selected_id),
            key="step_selector",
        )
        st.session_state.selected_step_id = selected_label

        # Get selected step image
        sel_step = state.step(selected_label)
        img_bgra = sel_step.image if sel_step else None

        if img_bgra is not None:
            if img_bgra.ndim == 2:
                img_to_encode = cv2.cvtColor(img_bgra, cv2.COLOR_GRAY2BGRA)
            elif img_bgra.shape[2] == 3:
                img_to_encode = cv2.cvtColor(img_bgra, cv2.COLOR_BGR2BGRA)
            else:
                img_to_encode = img_bgra

            success, buf = cv2.imencode(".png", img_to_encode)
            if success:
                b64 = base64.b64encode(buf.tobytes()).decode("utf-8")
                img_h, img_w = img_to_encode.shape[:2]
                canvas_html = render_canvas_html(img_w, img_h, b64)
                st.components.v1.html(canvas_html, height=700, scrolling=False)

    elif png_file is not None:
        # Show raw uploaded PNG as preview
        file_bytes = np.frombuffer(png_file.getvalue(), np.uint8)
        raw_img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if raw_img is not None:
            # Convert to BGRA for display (same as pipeline viewer)
            img_bgra = cv2.cvtColor(raw_img, cv2.COLOR_BGR2BGRA)
            success, buf = cv2.imencode(".png", img_bgra)
            if success:
                b64 = base64.b64encode(buf.tobytes()).decode("utf-8")
                img_h, img_w = img_bgra.shape[:2]
                canvas_html = render_canvas_html(img_w, img_h, b64)
                st.info("📄 Preview — Upload CSV file and click ▶ Run to process the image.")
                st.components.v1.html(canvas_html, height=700, scrolling=False)
        else:
            st.error("Could not decode uploaded PNG file.")
    else:
        st.markdown(
            '<div style="height:450px;display:flex;align-items:center;justify-content:center;'
            'background:#1a1f2e;border-radius:10px;color:#3d5068;font-size:0.95rem;">'
            'No image to display — upload PNG and CSV files, then click ▶ Run.'
            '</div>',
            unsafe_allow_html=True,
        )

    # ── Statistics ────────────────────────────────────────────────────────────
    if state is not None:
        st.markdown('<div class="section-title">📊 Statistics</div>', unsafe_allow_html=True)

        def _stat(step_id: int, key: str, default: str = "—") -> str:
            s = state.step(step_id)
            if s and s.success and key in s.stats:
                return str(s.stats[key])
            return default

        stat_rows = [
            ("Contours", _stat(7, "Total contours")),
            ("Candidates", _stat(8, "Passed")),
            ("Detected", _stat(13, "Detected fiducials")),
            ("RMSE", _stat(18, "RMSE")),
            ("Scale", _stat(18, "Scale")),
            ("Transform", _stat(18, "Type")),
        ]

        cols = st.columns(6)
        for i, (label, val) in enumerate(stat_rows):
            with cols[i]:
                st.markdown(
                    f'<div class="metric-card">'
                    f'<div class="mval">{val}</div>'
                    f'<div class="mlabel">{label}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ── Downloads ─────────────────────────────────────────────────────────────
    if state is not None and state.success:
        st.markdown('<div class="section-title">⬇ Downloads</div>', unsafe_allow_html=True)
        dl_cols = st.columns(3)

        def _img_to_bytes(step_id: int) -> bytes | None:
            s = state.step(step_id)
            if s and s.success and s.image is not None:
                ok, buf = cv2.imencode(".png", s.image)
                return buf.tobytes() if ok else None
            return None

        with dl_cols[0]:
            b = _img_to_bytes(13)
            if b:
                st.download_button("⬇ Download Annotated PNG", b, "annotated.png", "image/png",
                                   use_container_width=True)
        with dl_cols[1]:
            s19 = state.step(19)
            if s19 and s19.success:
                json_data = None
                if hasattr(s19, "json_bytes") and s19.json_bytes:
                    json_data = s19.json_bytes
                elif hasattr(s19, "output_path") and s19.output_path:
                    try:
                        json_data = Path(s19.output_path).read_bytes()
                    except Exception:
                        pass
                if json_data:
                    layer_name = str(s19.stats.get("Layer", "TOP")).upper()
                    layer_prefix = "BOT" if "BOT" in layer_name else "TOP"
                    fn = f"{layer_prefix}_origin.json"
                    st.download_button(
                        f"⬇ Download {fn}",
                        data=json_data,
                        file_name=fn,
                        mime="application/json",
                        use_container_width=True,
                    )
        with dl_cols[2]:
            b = _img_to_bytes(22)
            if b:
                st.download_button("⬇ Download Final PNG", b, "final.png", "image/png",
                                   use_container_width=True)

# ── TAB 2: Pipeline Steps & Execution Logs ───────────────────────────────────
with tab2:
    st.markdown("#### Pipeline Execution Steps")

    if state is None:
        st.markdown(
            '<p style="color:#4a6080;font-size:0.85rem;">Upload files and click ▶ Run to start.</p>',
            unsafe_allow_html=True,
        )
    else:
        all_step_ids = list(range(1, 23))

        for step_id in all_step_ids:
            s = state.step(step_id)
            if s is None:
                row_class = "pending"
                icon = "⬜"
                label = f"{step_id:02d}. —"
                dur = ""
            elif not s.success:
                row_class = "failed"
                icon = "❌"
                label = f"{step_id:02d}. {s.step_label}"
                dur = f"{s.duration_ms:.0f}ms"
            else:
                row_class = ""
                icon = "✅"
                label = f"{step_id:02d}. {s.step_label}"
                dur = f"{s.duration_ms:.0f}ms"

            st.markdown(
                f'<div class="step-row {row_class}">'
                f'<span class="icon">{icon}</span>'
                f'<span class="label">{label}</span>'
                f'<span class="dur">{dur}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            if s is not None and not s.success and s.error:
                st.markdown(
                    f'<div style="margin-left:30px;margin-bottom:4px;'
                    f'color:#ff6b6b;font-size:0.78rem;font-family:monospace;">'
                    f'↳ {s.error}</div>',
                    unsafe_allow_html=True,
                )

        if state is not None:
            status_color = "#4ecdc4" if state.success else "#ff6b6b"
            status_text = "✓ Complete" if state.success else f"✗ Failed at step {state.failed_at}"
            st.markdown(
                f'<div style="margin-top:14px;padding:10px 14px;border-radius:6px;'
                f'background:rgba(255,255,255,0.04);display:flex;justify-content:space-between;">'
                f'<span style="color:{status_color};font-size:0.85rem;font-weight:600;">{status_text}</span>'
                f'<span style="color:#4ecdc4;font-size:0.85rem;font-family:monospace;">'
                f'Total Duration: {state.total_duration_ms:.0f}ms</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown('<div class="section-title">📋 Detailed Step Logs</div>', unsafe_allow_html=True)
        for s in state.steps:
            if not s.logs:
                continue
            with st.expander(
                f"{'✅' if s.success else '❌'} Step {s.step_id}: {s.step_label}",
                expanded=not s.success or s.step_id == 19,
            ):
                log_html = ""
                for line in s.logs:
                    if "[ERROR]" in line:
                        cls = "log-error"
                    elif "[WARNING]" in line:
                        cls = "log-warning"
                    elif "[DEBUG]" in line:
                        cls = "log-debug"
                    else:
                        cls = "log-info"
                    log_html += (
                        f'<div class="{cls}" style="font-family:\'JetBrains Mono\','
                        f'monospace;font-size:0.80rem;line-height:1.6;white-space:pre-wrap;">{line}</div>'
                    )
                st.markdown(log_html, unsafe_allow_html=True)

