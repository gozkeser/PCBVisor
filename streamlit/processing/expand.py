"""
PCBVisor — Image Expansion Processing (Steps 1–4)

Steps:
    1. Load Image
    2. Convert to BGRA
    3. Color Keying (transparency)
    4. Canvas Expansion (padding)

Written from scratch — does not import or call expand_image.py.
"""

import time
from pathlib import Path

import cv2
import numpy as np

from .logger import PipelineLogger
from .results import (
    CanvasExpandResult,
    ColorKeyResult,
    ConvertBGRAResult,
    LoadImageResult,
)

# Step IDs for this group
STEP_LOAD = 1
STEP_BGRA = 2
STEP_COLOR_KEY = 3
STEP_EXPAND = 4


def run_load_image(
    image_bytes: bytes,
    filename: str,
    logger: PipelineLogger,
) -> LoadImageResult:
    """
    Step 1 — Load the uploaded PNG image from raw bytes.
    Returns the image as a BGRA numpy array.
    """
    t0 = time.perf_counter()
    logger.info(f"Loading image: {filename}")

    try:
        buf = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise ValueError("Could not decode image bytes — unsupported format.")

        h, w = img.shape[:2]
        ch = 1 if img.ndim == 2 else img.shape[2]
        duration = (time.perf_counter() - t0) * 1000
        logger.info(f"Loaded: {w}x{h} px, {ch} channel(s)")

        return LoadImageResult(
            step_id=STEP_LOAD,
            step_label="Load Image",
            success=True,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=img,
            stats={"Width": w, "Height": h, "Channels": ch},
            width=w,
            height=h,
            channels=ch,
        )
    except Exception as exc:
        duration = (time.perf_counter() - t0) * 1000
        logger.error(f"Failed to load image: {exc}")
        return LoadImageResult(
            step_id=STEP_LOAD,
            step_label="Load Image",
            success=False,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=None,
            stats={},
            error=str(exc),
        )


def run_convert_bgra(
    img: np.ndarray,
    logger: PipelineLogger,
) -> ConvertBGRAResult:
    """
    Step 2 — Ensure image is 4-channel BGRA.
    Handles grayscale, BGR (3-channel), and existing BGRA inputs.
    """
    t0 = time.perf_counter()
    logger.info("Converting image to BGRA format")

    try:
        if img.ndim == 2:
            logger.info("Source is Grayscale — converting via COLOR_GRAY2BGRA")
            out = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
        elif img.shape[2] == 3:
            logger.info("Source is BGR — converting via COLOR_BGR2BGRA")
            out = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
        elif img.shape[2] == 4:
            logger.info("Source is already BGRA — no conversion needed")
            out = img.copy()
        else:
            raise ValueError(f"Unsupported channel count: {img.shape[2]}")

        duration = (time.perf_counter() - t0) * 1000
        return ConvertBGRAResult(
            step_id=STEP_BGRA,
            step_label="Convert to BGRA",
            success=True,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=out,
            stats={"Output channels": 4},
        )
    except Exception as exc:
        duration = (time.perf_counter() - t0) * 1000
        logger.error(f"Conversion failed: {exc}")
        return ConvertBGRAResult(
            step_id=STEP_BGRA,
            step_label="Convert to BGRA",
            success=False,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=None,
            stats={},
            error=str(exc),
        )


def run_color_key(
    img: np.ndarray,
    transparent_rgb: tuple[int, int, int],
    tolerance: int = 0,
    logger: PipelineLogger = None,
) -> ColorKeyResult:
    """
    Step 3 — Set alpha channel to 0 for all pixels matching the specified RGB color within tolerance.
    """
    t0 = time.perf_counter()
    r, g, b = transparent_rgb
    if logger:
        logger.info(f"Applying color keying for RGB ({r}, {g}, {b}) with tolerance ±{tolerance}")

    try:
        out = img.copy()
        b_ch = out[:, :, 0].astype(int)
        g_ch = out[:, :, 1].astype(int)
        r_ch = out[:, :, 2].astype(int)

        mask = (
            (np.abs(b_ch - b) <= tolerance) &
            (np.abs(g_ch - g) <= tolerance) &
            (np.abs(r_ch - r) <= tolerance)
        )
        out[mask, 3] = 0
        count = int(mask.sum())
        if logger:
            logger.info(f"Made {count:,} pixels transparent")

        duration = (time.perf_counter() - t0) * 1000
        logs = logger.get_lines() if logger else []

        return ColorKeyResult(
            step_id=STEP_COLOR_KEY,
            step_label="Color Keying",
            success=True,
            duration_ms=duration,
            logs=logs,
            image=out,
            stats={"Target color": f"rgb({r},{g},{b})", "Tolerance": f"±{tolerance}", "Transparent pixels": count},
            transparent_pixels=count,
        )
    except Exception as exc:
        duration = (time.perf_counter() - t0) * 1000
        logs = logger.get_lines() if logger else []
        if logger:
            logger.error(f"Color keying failed: {exc}")
        return ColorKeyResult(
            step_id=STEP_COLOR_KEY,
            step_label="Color Keying",
            success=False,
            duration_ms=duration,
            logs=logs,
            image=None,
            stats={},
            error=str(exc),
        )


def run_canvas_expand(
    img: np.ndarray,
    padding: int,
    logger: PipelineLogger,
) -> CanvasExpandResult:
    """
    Step 4 — Add transparent border padding around the image on all four sides.
    """
    t0 = time.perf_counter()
    logger.info(f"Expanding canvas by {padding} px on all sides")

    try:
        if padding == 0:
            logger.info("Padding is 0 — skipping expansion")
            out = img.copy()
        else:
            out = cv2.copyMakeBorder(
                img,
                top=padding,
                bottom=padding,
                left=padding,
                right=padding,
                borderType=cv2.BORDER_CONSTANT,
                value=(0, 0, 0, 0),
            )

        h, w = out.shape[:2]
        logger.info(f"Output size: {w}x{h} px")
        duration = (time.perf_counter() - t0) * 1000

        return CanvasExpandResult(
            step_id=STEP_EXPAND,
            step_label="Canvas Expansion",
            success=True,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=out,
            stats={"New width": w, "New height": h, "Padding": f"{padding} px"},
            new_width=w,
            new_height=h,
            padding_px=padding,
        )
    except Exception as exc:
        duration = (time.perf_counter() - t0) * 1000
        logger.error(f"Canvas expansion failed: {exc}")
        return CanvasExpandResult(
            step_id=STEP_EXPAND,
            step_label="Canvas Expansion",
            success=False,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=None,
            stats={},
            error=str(exc),
        )
