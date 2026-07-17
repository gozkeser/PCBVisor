"""
PCBVisor — Final Annotation / Display Processing (Steps 20–22)

Steps:
    20. Load Image for Display
    21. Draw Origin Marker
    22. Draw Fiducial Markers

Written from scratch — does not import or call fid_display.py.
All display parameters are passed explicitly (no hardcoded constants).
"""

import json
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from .logger import PipelineLogger
from .results import DrawFiducialsResult, DrawOriginResult, LoadForDisplayResult

# Step IDs
STEP_LOAD_DISPLAY = 20
STEP_DRAW_ORIGIN = 21
STEP_DRAW_FIDUCIALS = 22


# ─── Step 20 — Load Image for Display ────────────────────────────────────────

def run_load_for_display(
    img_bgra: np.ndarray,
    logger: PipelineLogger,
) -> LoadForDisplayResult:
    """
    Step 20 — Accept the expanded BGRA image (from Step 4) for display annotation.
    Creates a fresh copy so upstream results are not mutated.
    """
    t0 = time.perf_counter()
    logger.info("Preparing image for final display annotation")

    try:
        display = img_bgra.copy()
        h, w = display.shape[:2]
        logger.info(f"Image ready: {w}x{h} px")
        duration = (time.perf_counter() - t0) * 1000

        return LoadForDisplayResult(
            step_id=STEP_LOAD_DISPLAY,
            step_label="Load Image for Display",
            success=True,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=display,
            stats={"Width": w, "Height": h},
            width=w,
            height=h,
        )
    except Exception as exc:
        duration = (time.perf_counter() - t0) * 1000
        logger.error(f"Load for display failed: {exc}")
        return LoadForDisplayResult(
            step_id=STEP_LOAD_DISPLAY,
            step_label="Load Image for Display",
            success=False,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=None,
            stats={},
            error=str(exc),
        )


# ─── Marker Drawing Helpers ────────────────────────────────────────────────────

def _parse_hex_color(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    """Convert #RRGGBB to (B, G, R, A) for OpenCV BGRA."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return (b, g, r, alpha)


def _draw_fiducial_marker(
    img: np.ndarray,
    center: tuple[int, int],
    R: float,
    shape: str,
    color: tuple[int, int, int, int],
    thickness: int,
    size_multiplier: float,
) -> None:
    """Draw a single fiducial marker on the image in-place."""
    cx, cy = center
    r_px = max(int(R), 1)
    L = int(R * size_multiplier)

    if shape == "circle":
        cv2.circle(img, (cx, cy), r_px, color, thickness)

    elif shape == "concentric":
        cv2.circle(img, (cx, cy), r_px, color, thickness)
        cv2.circle(img, (cx, cy), L, color, thickness)

    elif shape == "reticle":
        cv2.circle(img, (cx, cy), r_px, color, thickness)
        cv2.line(img, (cx - L, cy), (cx + L, cy), color, thickness)
        cv2.line(img, (cx, cy - L), (cx, cy + L), color, thickness)

    elif shape == "target":
        cv2.circle(img, (cx, cy), r_px, color, thickness)
        cv2.circle(img, (cx, cy), L, color, thickness)
        L2 = int(R * size_multiplier * 1.5)
        cv2.line(img, (cx - L2, cy), (cx + L2, cy), color, thickness)
        cv2.line(img, (cx, cy - L2), (cx, cy + L2), color, thickness)


def _draw_origin_marker(
    img: np.ndarray,
    cx: int,
    cy: int,
    M: np.ndarray,
    scale: float,
    size: int,
    color: tuple[int, int, int, int],
    thickness: int,
) -> None:
    """Draw origin crosshair with axis arrows in-place."""
    L = size * 2
    cv2.circle(img, (cx, cy), 5, color, -1)
    cv2.circle(img, (cx, cy), size, color, thickness)

    dx_x = (M[0, 0] / max(scale, 1e-6)) * L
    dy_x = (M[1, 0] / max(scale, 1e-6)) * L
    dx_y = (M[0, 1] / max(scale, 1e-6)) * L
    dy_y = (M[1, 1] / max(scale, 1e-6)) * L

    tx = (int(round(cx + dx_x)), int(round(cy + dy_x)))
    ty = (int(round(cx + dx_y)), int(round(cy + dy_y)))

    cv2.arrowedLine(img, (cx, cy), tx, color, thickness, tipLength=0.15)
    cv2.arrowedLine(img, (cx, cy), ty, color, thickness, tipLength=0.15)

    cv2.putText(img, "X", (tx[0] + (10 if dx_x >= 0 else -18), tx[1] + 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, thickness)
    cv2.putText(img, "Y", (ty[0] + (10 if dx_y >= 0 else -18), ty[1] + 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, thickness)
    cv2.putText(img, "ORIGIN (0,0)", (cx + 25, cy - 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, thickness + 1)


# ─── Step 21 — Draw Origin Marker ─────────────────────────────────────────────

def run_draw_origin(
    img_bgra: np.ndarray,
    origin_json_path: Path,
    origin_marker_size: int,
    origin_color_hex: str,
    line_thickness: int,
    logger: PipelineLogger,
) -> tuple[DrawOriginResult, np.ndarray, Optional[np.ndarray]]:
    """
    Step 21 — Read the origin JSON and draw the origin marker on the image.
    Returns (result, annotated_image, M_matrix).
    """
    t0 = time.perf_counter()
    logger.info(f"Drawing origin marker from: {origin_json_path.name}")

    try:
        with open(origin_json_path, "r", encoding="utf-8") as f:
            json_data = json.load(f)

        M = np.array(json_data["transformation_matrix"], dtype=np.float64)
        origin_px = json_data["origin_pixel"]
        orig_x = int(round(origin_px["x"]))
        orig_y = int(round(origin_px["y"]))
        scale = float(np.sqrt(M[0, 0] ** 2 + M[1, 0] ** 2))

        color = _parse_hex_color(origin_color_hex)

        display = img_bgra.copy()
        h, w = display.shape[:2]

        # Expand canvas if origin is slightly out of bounds
        pad_top = pad_bottom = pad_left = pad_right = 0
        if -100 <= orig_x < 0:
            pad_left = 100
        elif w <= orig_x < w + 100:
            pad_right = 100
        if -100 <= orig_y < 0:
            pad_top = 100
        elif h <= orig_y < h + 100:
            pad_bottom = 100

        if any([pad_top, pad_bottom, pad_left, pad_right]):
            display = cv2.copyMakeBorder(
                display, pad_top, pad_bottom, pad_left, pad_right,
                borderType=cv2.BORDER_CONSTANT, value=[0, 0, 0, 0]
            )
            orig_x += pad_left
            orig_y += pad_top
            logger.info(f"Canvas expanded (top={pad_top}, bottom={pad_bottom}, "
                        f"left={pad_left}, right={pad_right}) to fit origin")

        h2, w2 = display.shape[:2]
        in_bounds = 0 <= orig_x < w2 and 0 <= orig_y < h2

        if in_bounds:
            _draw_origin_marker(display, orig_x, orig_y, M, scale,
                                 origin_marker_size, color, line_thickness)
            logger.info(f"Origin drawn at ({orig_x}, {orig_y}) px")
        else:
            logger.warning(f"Origin ({orig_x}, {orig_y}) is outside image bounds — skipped")

        duration = (time.perf_counter() - t0) * 1000
        result = DrawOriginResult(
            step_id=STEP_DRAW_ORIGIN,
            step_label="Draw Origin Marker",
            success=True,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=display,
            stats={"Origin X": orig_x, "Origin Y": orig_y, "In bounds": in_bounds},
            origin_in_bounds=in_bounds,
            origin_x=orig_x,
            origin_y=orig_y,
        )
        return result, display, M

    except Exception as exc:
        duration = (time.perf_counter() - t0) * 1000
        logger.error(f"Draw origin failed: {exc}")
        result = DrawOriginResult(
            step_id=STEP_DRAW_ORIGIN,
            step_label="Draw Origin Marker",
            success=False,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=img_bgra.copy(),
            stats={},
            error=str(exc),
        )
        return result, img_bgra.copy(), None


# ─── Step 22 — Draw Fiducial Markers ─────────────────────────────────────────

def run_draw_fiducials(
    img_bgra: np.ndarray,
    origin_json_path: Path,
    marker_shape: str,
    fiducial_color_hex: str,
    line_thickness: int,
    marker_size_multiplier: float,
    fiducial_radius_offset: int,
    show_labels: bool,
    show_coordinates: bool,
    logger: PipelineLogger,
) -> DrawFiducialsResult:
    """
    Step 22 — Draw fiducial marker shapes on the image from origin JSON data.
    """
    t0 = time.perf_counter()
    logger.info("Drawing fiducial markers")

    try:
        with open(origin_json_path, "r", encoding="utf-8") as f:
            json_data = json.load(f)

        M = np.array(json_data["transformation_matrix"], dtype=np.float64)
        matched_fiducials = json_data.get("matched_fiducials", [])
        scale = float(np.sqrt(M[0, 0] ** 2 + M[1, 0] ** 2))
        fid_color = _parse_hex_color(fiducial_color_hex)
        text_color = (255, 255, 255, 255)

        display = img_bgra.copy()
        h, w = display.shape[:2]
        drawn = 0

        for rf in matched_fiducials:
            designator = rf.get("designator", "FD")
            cx_raw = rf["x_px"]
            cy_raw = rf["y_px"]
            cx = int(round(cx_raw))
            cy = int(round(cy_raw))

            base_radius = rf.get("radius_px", scale * 0.5)
            R = base_radius + fiducial_radius_offset

            if 0 <= cx < w and 0 <= cy < h:
                _draw_fiducial_marker(
                    display, (cx, cy), R,
                    shape=marker_shape,
                    color=fid_color,
                    thickness=line_thickness,
                    size_multiplier=marker_size_multiplier,
                )

                label = ""
                if show_labels:
                    label += designator
                if show_coordinates:
                    A = np.array([[M[0, 0], M[0, 1]], [M[1, 0], M[1, 1]]], dtype=np.float64)
                    B = np.array([cx_raw - M[0, 2], cy_raw - M[1, 2]], dtype=np.float64)
                    try:
                        x_mm, y_mm = np.linalg.solve(A, B)
                        label += f" ({x_mm:.1f},{y_mm:.1f})"
                    except np.linalg.LinAlgError:
                        pass

                if label:
                    cv2.putText(display, label, (cx + 5, cy - 15),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, text_color, line_thickness,
                                cv2.LINE_AA)

                logger.info(f"  {designator} drawn at ({cx}, {cy}) R={R:.1f}")
                drawn += 1
            else:
                logger.warning(f"  {designator} at ({cx},{cy}) outside image bounds")

        logger.info(f"Total fiducials drawn: {drawn}")
        duration = (time.perf_counter() - t0) * 1000

        return DrawFiducialsResult(
            step_id=STEP_DRAW_FIDUCIALS,
            step_label="Draw Fiducial Markers",
            success=True,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=display,
            stats={"Fiducials drawn": drawn, "Shape": marker_shape},
            fiducials_drawn=drawn,
        )

    except Exception as exc:
        duration = (time.perf_counter() - t0) * 1000
        logger.error(f"Draw fiducials failed: {exc}")
        return DrawFiducialsResult(
            step_id=STEP_DRAW_FIDUCIALS,
            step_label="Draw Fiducial Markers",
            success=False,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=None,
            stats={},
            error=str(exc),
        )
