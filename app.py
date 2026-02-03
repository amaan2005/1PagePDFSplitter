import io
import os
from typing import Optional
import streamlit as st
import fitz  # PyMuPDF
from PIL import Image, ImageDraw
from streamlit_image_coordinates import streamlit_image_coordinates

st.set_page_config(page_title="PDF1PageSplitter", layout="wide")
Image.MAX_IMAGE_PIXELS = 300_000_000
st.markdown('<div id="top"></div>', unsafe_allow_html=True)
st.markdown(
    """
    <style>
      .block-container {max-width: 100%; padding-left: 2rem; padding-right: 2rem; padding-top: 1.25rem;}
      .main .block-container {padding-bottom: 1.25rem;}
      .block-container > div {margin-bottom: 0.25rem;}
      .pdf-view {
        margin-left: -2rem;
        margin-right: -2rem;
        padding-left: 0.5rem;
        padding-right: 0.5rem;
      }
      img {max-width: 100%; height: auto;}
      .settings-subtle {
        color: #666666;
        font-size: 0.9rem;
      }
      .btn-link {
        display: inline-block;
        background: #ffffff;
        color: #222222 !important;
        border: 1px solid #e6e6e6;
        border-radius: 8px;
        padding: 0.45rem 0.9rem;
        text-decoration: none !important;
        font-weight: 400 !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.06);
      }
      .btn-link:hover {
        border-color: #d0d0d0;
        background: #fafafa;
      }
      .stDownloadButton button {
        box-shadow: 0 0 12px rgba(59, 130, 246, 0.45), 0 0 24px rgba(59, 130, 246, 0.25);
      }
      /* Prevent caret blink in select inputs (e.g., Image format) */
      .stSelectbox div[data-baseweb="select"] input {
        caret-color: transparent;
      }
      .stSelectbox div[data-baseweb="select"] input:focus {
        outline: none;
        box-shadow: none;
      }
      .app-footer {
        position: fixed;
        left: 0;
        right: 0;
        bottom: 8px;
        text-align: center;
        color: #888;
        font-size: 0.85rem;
        pointer-events: none;
      }
      .to-top {
        position: fixed;
        right: 14px;
        bottom: 56px;
        width: 36px;
        height: 36px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #ffffff;
        color: #222222 !important;
        border: 1px solid #e6e6e6;
        border-radius: 999px;
        text-decoration: none !important;
        font-weight: 600;
        box-shadow: 0 2px 8px rgba(0,0,0,0.12);
        z-index: 9999;
        pointer-events: auto;
        opacity: 1;
        visibility: visible;
        transition: opacity 0.2s ease;
      }
      .to-top:hover {
        border-color: #d0d0d0;
        background: #fafafa;
      }
      .to-top.show { opacity: 1; visibility: visible; }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("📄 PDF1PageSplitter")
st.caption("Upload a **1-page long PDF** → click to add horizontal cut lines → export as a multi-page PDF.")
if os.getenv("APP_MODE", "").lower() == "cloud":
    st.info("This version runs on the cloud. Do not upload sensitive documents. For private/offline use, use the app build. ")
st.markdown(
    '<div class="app-footer">Copyright © 2026 helenthetuxedo on Instagram.</div>',
    unsafe_allow_html=True,
)
st.markdown(
    """
    <a class="to-top" href="#top" id="to-top-btn" aria-label="Back to top">↑</a>
    <script>
      (function () {
        const btn = document.getElementById('to-top-btn');
        if (btn && btn.querySelector('svg') === null) {
          btn.innerHTML =
            '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">' +
            '<path d="M12 6l-7 7h4v5h6v-5h4z" fill="#222"/></svg>';
        }
      })();
    </script>
    <script>
      (function () {
        const btn = document.getElementById('to-top-btn');
        if (btn) btn.classList.add('show');
      })();
    </script>
    """,
    unsafe_allow_html=True,
)

QUALITY_PRESETS = {
    "Low (120 DPI)": {"dpi": 120, "comp": 0.20, "jpg_q": 70},
    "Normal (170 DPI)": {"dpi": 170, "comp": 0.28, "jpg_q": 80},
    "High (220 DPI)": {"dpi": 220, "comp": 0.38, "jpg_q": 88},
    "Native (300 DPI)": {"dpi": 300, "comp": 0.55, "jpg_q": 95},
    "Gradescope (Dynamic, 100MB)": {"dpi": 220, "comp": 0.38, "jpg_q": 80},
}

@st.cache_data(show_spinner=False)
def render_page_image(pdf_bytes: bytes, dpi: int, max_pixels: Optional[int] = None) -> Image.Image:
    # Expensive step: rasterizing the PDF. Cache this so clicks don't re-render.
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = doc.load_page(0)
        zoom = dpi / 72.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    finally:
        doc.close()

    if max_pixels is not None:
        total = img.width * img.height
        if total > max_pixels:
            s = (max_pixels / total) ** 0.5
            new_w = max(1, int(img.width * s))
            new_h = max(1, int(img.height * s))
            img = img.resize((new_w, new_h), Image.LANCZOS)
    return img

def estimate_mb(width_px: int, height_px: int, num_pages: int, comp: float) -> float:
    total_pixels = width_px * height_px
    raw_bytes = total_pixels * 3
    est_bytes = raw_bytes * comp
    overhead = num_pages * 60_000  # rough per-page PDF overhead
    return (est_bytes + overhead) / 1_000_000

def build_output_pdf_from_slices(
    slices: list[Image.Image],
    px_to_pt: float,
    img_format: str,
    jpg_quality: int,
) -> bytes:
    out = fitz.open()
    for crop in slices:
        buf = io.BytesIO()
        if img_format == "PNG":
            crop.save(buf, format="PNG")
        else:
            crop.save(buf, format="JPEG", quality=jpg_quality, optimize=True)
        img_bytes = buf.getvalue()

        out_w_pt = crop.width * px_to_pt
        out_h_pt = crop.height * px_to_pt
        p = out.new_page(width=out_w_pt, height=out_h_pt)
        p.insert_image(fitz.Rect(0, 0, out_w_pt, out_h_pt), stream=img_bytes)
    return out.tobytes()

uploaded = st.file_uploader("Drop a 1-page PDF here", type=["pdf"])
if not uploaded:
    st.stop()

pdf_bytes = uploaded.read()
doc = fitz.open(stream=pdf_bytes, filetype="pdf")
page = doc.load_page(0)
page_w_pt = page.rect.width
page_h_pt = page.rect.height

if doc.page_count != 1:
    st.error(f"This tool ONLY supports PDFs with exactly 1 page. Yours has {doc.page_count} pages.")
    st.stop()

base_name = uploaded.name.rsplit(".", 1)[0]

st.subheader("Settings")
c1, c2 = st.columns([1, 1], gap="large")
with c1:
    st.markdown('<span class="settings-subtle">Output page size adapts to each cut.</span>', unsafe_allow_html=True)
    quality_label = st.selectbox("Export quality", list(QUALITY_PRESETS.keys()), index=2)
    dpi = QUALITY_PRESETS[quality_label]["dpi"]
    comp = QUALITY_PRESETS[quality_label]["comp"]
    jpg_quality = QUALITY_PRESETS[quality_label]["jpg_q"]
    gs_selected = quality_label.startswith("Gradescope")
    if gs_selected:
        if not st.session_state.get("gs_was_selected", False):
            st.session_state["img_format_prev"] = st.session_state.get(
                "img_format_select", "JPEG (smaller, Default)"
            )
        st.session_state["img_format_select"] = "JPEG (smaller, Default)"
        st.selectbox(
            "Image format (inside PDF)",
            ["JPEG (smaller, Default)", "PNG (lossless)"],
            index=0,
            disabled=True,
            key="img_format_select",
        )
        img_format_choice = "JPEG (smaller, Default)"
    else:
        if st.session_state.get("gs_was_selected", False) and "img_format_prev" in st.session_state:
            st.session_state["img_format_select"] = st.session_state["img_format_prev"]
        img_format_choice = st.selectbox(
            "Image format (inside PDF)",
            ["JPEG (smaller, Default)", "PNG (lossless)"],
            index=0,
            key="img_format_select",
        )
    st.session_state["gs_was_selected"] = gs_selected
    img_format = "PNG" if img_format_choice.startswith("PNG") else "JPEG"
    display_dpi = min(dpi, 320)
    st.write("**Controls**")
    if st.button("Undo last cut"):
        if "cuts_y" in st.session_state and st.session_state.cuts_y:
            st.session_state.cuts_y.pop()
    if st.button("Clear cuts"):
        st.session_state.cuts_y = []
with c2:
    st.markdown('<div style="height: 0.5rem;"></div>', unsafe_allow_html=True)

st.caption("Tip: click once where you want a new page to start. A horizontal line will appear.")
export_slot = st.empty()
export_clicked = st.button("Export multi-page PDF")

st.markdown('<div class="pdf-view">', unsafe_allow_html=True)
st.divider()
st.markdown('<div id="cutlines-marker"></div>', unsafe_allow_html=True)
st.subheader("Click to add cut lines (scroll to move down)")

# Render full page for display (cached) and keep it reasonably sized for responsiveness.
img = render_page_image(pdf_bytes, dpi=display_dpi, max_pixels=10_000_000)
W, H = img.size

if "cuts_y" not in st.session_state:
    st.session_state.cuts_y = []  # Y as fraction of page height (0..1)
if "last_click" not in st.session_state:
    st.session_state.last_click = None
if st.session_state.cuts_y and max(st.session_state.cuts_y) > 1:
    st.session_state.cuts_y = [y / H for y in st.session_state.cuts_y]

# Keep the interactive preview lightweight; huge widths make every rerun slow.
display_width = min(1600, W)
scale = display_width / W
display_height = int(H * scale)

# Create overlay with cut lines
display_img = img.resize((display_width, display_height))
overlay = display_img.copy()
draw = ImageDraw.Draw(overlay)

# Draw existing cuts
for y_frac in st.session_state.cuts_y:
    y_disp = int(y_frac * display_height)
    draw.line([(0, y_disp), (display_width, y_disp)], fill=(255, 0, 0), width=2)

est_pages = max(1, len(st.session_state.cuts_y) + 1)
st.caption(
    f"Rendered: {W}×{H}px · Cuts: {len(st.session_state.cuts_y)}"
)

# Clickable image: returns {"x":..., "y":...} in DISPLAY coords
click = streamlit_image_coordinates(overlay, key="clickable", width=display_width)
st.markdown('</div>', unsafe_allow_html=True)

if click and "y" in click:
    click_x = int(click.get("x", -1))
    click_y = int(click["y"])
    if st.session_state.last_click != (click_x, click_y):
        st.session_state.last_click = (click_x, click_y)
        y_disp = click_y
        y_orig = int(round(y_disp / scale))
        y_frac = y_orig / H

        # Add cut if not too close to existing ones (debounce)
        if 0 < y_orig < H:
            before = list(st.session_state.cuts_y)
            cuts = sorted(before + [y_frac])
            filtered = []
            for c in cuts:
                if not filtered or abs((c * display_height) - (filtered[-1] * display_height)) > 12:
                    filtered.append(c)
            st.session_state.cuts_y = filtered
            if st.session_state.cuts_y != before:
                st.rerun()

if export_clicked:
    cuts = sorted([y for y in st.session_state.cuts_y if 0 < y < 1])

    # Build slices based on cuts: [0..cut1], [cut1..cut2], ... [last..H]
    ranges = []
    start = 0
    for y in cuts:
        ranges.append((start, y))
        start = y
    ranges.append((start, 1.0))

    # Render once at the starting dpi; for Gradescope retries, downscale this image instead of re-rendering.
    base_dpi = dpi
    _ = render_page_image(pdf_bytes, dpi=base_dpi, max_pixels=None)  # warm cache for export

    def export_with_dpi(dpi_value: int, jpg_q: int) -> bytes:
        export_w_px = int(page_w_pt * dpi_value / 72.0)
        export_h_px = int(page_h_pt * dpi_value / 72.0)

        max_export_pixels = 250_000_000
        total_export_px = export_w_px * export_h_px
        if total_export_px > max_export_pixels:
            s = (max_export_pixels / total_export_px) ** 0.5
            dpi_value = max(72, int(dpi_value * s))
            export_w_px = int(page_w_pt * dpi_value / 72.0)
            export_h_px = int(page_h_pt * dpi_value / 72.0)

        # Render the PDF once at base_dpi (cached). If we need a smaller dpi, downscale.
        export_img = render_page_image(pdf_bytes, dpi=base_dpi, max_pixels=None)
        if dpi_value != base_dpi:
            factor = dpi_value / float(base_dpi)
            new_w = max(1, int(export_img.width * factor))
            new_h = max(1, int(export_img.height * factor))
            export_img = export_img.resize((new_w, new_h), Image.LANCZOS)

        export_W, export_H = export_img.size

        slices = []
        for (y0, y1) in ranges:
            if (y1 - y0) * export_H < 2:  # ignore ultra-tiny slices
                continue
            y0_px = int(y0 * export_H)
            y1_px = int(y1 * export_H)
            crop = export_img.crop((0, y0_px, export_W, y1_px))
            slices.append(crop)

        px_to_pt = 72.0 / dpi_value
        return build_output_pdf_from_slices(slices, px_to_pt, img_format, jpg_q)

    out_bytes = export_with_dpi(dpi, jpg_quality)

    if quality_label.startswith("Gradescope"):
        target_mb = 100.0
        dpi_try = dpi
        jpg_q_try = min(jpg_quality, 85)
        last_dpi = None
        last_q = None
        while len(out_bytes) / 1_000_000 > target_mb:
            if dpi_try == last_dpi and jpg_q_try == last_q:
                break
            last_dpi = dpi_try
            last_q = jpg_q_try
            dpi_try = max(10, int(dpi_try * 0.80))
            jpg_q_try = max(30, jpg_q_try - 10)
            out_bytes = export_with_dpi(dpi_try, jpg_q_try)

    with export_slot:
        st.download_button(
            "Download PDF",
            data=out_bytes,
            file_name=f"{base_name}_split.pdf",
            mime="application/pdf",
        )

# Bottom tip
st.markdown('<div style="height: 16px;"></div>', unsafe_allow_html=True)
st.caption("Tip: use the floating ↑ button to jump to the top.")
