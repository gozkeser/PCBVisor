"""
PCBVisor — Fiducial Detection Processing (Steps 5–13)

Steps:
    5.  Grayscale Conversion
    6.  Edge Detection (Canny or Binary)
    7.  Contour Extraction
    8.  Circularity + Radius Filter
    9.  Deduplication
    10. Min-Enclosing Circle Filter
    11. Inner Circle Pick
    12. Proximity Coordinate Filter
    13. Annotate + Export JSON

Written from scratch — does not import or call fid_finder.py.
"""

import json
import time
from pathlib import Path

import cv2
import numpy as np

from .logger import PipelineLogger
from .results import (
    AnnotateResult,
    CircularityFilterResult,
    ContourResult,
    DeduplicateResult,
    EdgeResult,
    GrayscaleResult,
    InnerCirclePickResult,
    MinEnclosingFilterResult,
    ProximityFilterResult,
)

# Step IDs
STEP_GRAY = 5
STEP_EDGE = 6
STEP_CONTOUR = 7
STEP_CIRC_FILTER = 8
STEP_DEDUP = 9
STEP_MIN_ENCLOSING = 10
STEP_INNER_PICK = 11
STEP_PROXIMITY = 12
STEP_ANNOTATE = 13

# Detection colors (BGRA)
COLOR_GREEN = (0, 255, 0, 255)
COLOR_RED = (0, 0, 255, 255)
COLOR_BLUE = (255, 0, 0, 255)

# Proximity tolerance (pixels) — ~2.7 mm to filter 2.54 mm pitch connector pins
PROXIMITY_TOLERANCE = 64


def run_grayscale(img: np.ndarray, logger: PipelineLogger) -> GrayscaleResult:
    """Step 5 — Convert BGRA image to grayscale."""
    t0 = time.perf_counter()
    logger.info("Converting to grayscale")

    try:
        if img.ndim == 2:
            gray = img.copy()
        elif img.shape[2] == 4:
            gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
        else:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Render grayscale as BGRA for uniform display
        display = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGRA)
        if img.ndim == 3 and img.shape[2] == 4:
            display[:, :, 3] = img[:, :, 3]

        duration = (time.perf_counter() - t0) * 1000
        logger.info(f"Grayscale image: {gray.shape[1]}x{gray.shape[0]} px")

        return GrayscaleResult(
            step_id=STEP_GRAY,
            step_label="Grayscale Conversion",
            success=True,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=display,
            stats={"Output": "Grayscale"},
        )
    except Exception as exc:
        duration = (time.perf_counter() - t0) * 1000
        logger.error(f"Grayscale conversion failed: {exc}")
        return GrayscaleResult(
            step_id=STEP_GRAY,
            step_label="Grayscale Conversion",
            success=False,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=None,
            stats={},
            error=str(exc),
        )


def run_edge_detection(
    img_bgra: np.ndarray,
    method: str,
    canny_threshold: float,
    binary_threshold: int,
    binary_invert: bool,
    logger: PipelineLogger,
) -> EdgeResult:
    """
    Step 6 — Edge detection.

    method: "canny"  → Canny edge detection (upper threshold = canny_threshold)
            "binary" → Simple global threshold (cv2.THRESH_BINARY)
    """
    t0 = time.perf_counter()
    logger.info(f"Edge detection method: {method.upper()}")

    try:
        # Convert to grayscale first
        if img_bgra.ndim == 2:
            gray = img_bgra
        elif img_bgra.shape[2] == 4:
            gray = cv2.cvtColor(img_bgra, cv2.COLOR_BGRA2GRAY)
        else:
            gray = cv2.cvtColor(img_bgra, cv2.COLOR_BGR2GRAY)

        if method == "canny":
            upper = float(canny_threshold)
            lower = upper / 2.0
            edges = cv2.Canny(gray, lower, upper)
            label = f"Canny (upper={upper:.0f}, lower={lower:.0f})"
            threshold_val = upper
            logger.info(f"Canny thresholds — lower: {lower:.0f}, upper: {upper:.0f}")
        elif method == "binary":
            flag = cv2.THRESH_BINARY_INV if binary_invert else cv2.THRESH_BINARY
            _, edges = cv2.threshold(gray, binary_threshold, 255, flag)
            label = f"Binary (thresh={binary_threshold}, invert={binary_invert})"
            threshold_val = float(binary_threshold)
            logger.info(f"Binary threshold: {binary_threshold}, invert: {binary_invert}")
        else:
            raise ValueError(f"Unknown edge detection method: {method!r}")

        non_zero = int(np.count_nonzero(edges))
        logger.info(f"Edge pixels detected: {non_zero:,}")

        # Build display image (edge mask as BGRA)
        display = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGRA)
        if img_bgra.shape[2] == 4:
            display[:, :, 3] = img_bgra[:, :, 3]

        duration = (time.perf_counter() - t0) * 1000

        return EdgeResult(
            step_id=STEP_EDGE,
            step_label=f"Edge Detection",
            success=True,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=display,
            stats={"Method": label, "Edge pixels": non_zero},
            method=method,
            threshold=threshold_val,
            # Store edges array for next step (attach as extra attr via monkey-patch workaround)
        )
    except Exception as exc:
        duration = (time.perf_counter() - t0) * 1000
        logger.error(f"Edge detection failed: {exc}")
        return EdgeResult(
            step_id=STEP_EDGE,
            step_label="Edge Detection",
            success=False,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=None,
            stats={},
            error=str(exc),
        )


def run_contour_extraction(
    img_bgra: np.ndarray,
    edges: np.ndarray,
    logger: PipelineLogger,
) -> tuple[ContourResult, list]:
    """
    Step 7 — Extract all contours from the edge image.
    Returns (ContourResult, raw_contours_list).
    """
    t0 = time.perf_counter()
    logger.info("Extracting contours from edge image")

    try:
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        count = len(contours)
        logger.info(f"Found {count:,} contour(s)")

        # Draw all contours on a copy of the original image for visualization
        display = img_bgra.copy()
        # Draw contours in yellow on the original image
        bgr_display = cv2.cvtColor(display, cv2.COLOR_BGRA2BGR)
        cv2.drawContours(bgr_display, contours, -1, (0, 255, 255), 1)
        display = cv2.cvtColor(bgr_display, cv2.COLOR_BGR2BGRA)
        if img_bgra.shape[2] == 4:
            display[:, :, 3] = img_bgra[:, :, 3]

        duration = (time.perf_counter() - t0) * 1000

        result = ContourResult(
            step_id=STEP_CONTOUR,
            step_label="Contour Extraction",
            success=True,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=display,
            stats={"Total contours": count},
            total_contours=count,
        )
        return result, list(contours)

    except Exception as exc:
        duration = (time.perf_counter() - t0) * 1000
        logger.error(f"Contour extraction failed: {exc}")
        result = ContourResult(
            step_id=STEP_CONTOUR,
            step_label="Contour Extraction",
            success=False,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=None,
            stats={},
            error=str(exc),
        )
        return result, []


def run_circularity_filter(
    img_bgra: np.ndarray,
    contours: list,
    min_circularity: float,
    min_radius: int,
    max_radius: int,
    logger: PipelineLogger,
) -> tuple[CircularityFilterResult, list]:
    """
    Step 8 — Filter contours by circularity and radius constraints.
    Returns (CircularityFilterResult, candidates) where candidates = list of (x, y, r, area).
    """
    t0 = time.perf_counter()
    logger.info(
        f"Filtering by circularity >= {min_circularity}, "
        f"radius [{min_radius}–{max_radius}] px"
    )

    try:
        candidates: list[tuple[float, float, float, float]] = []

        for contour in contours:
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)
            if perimeter == 0:
                continue
            circularity = (4 * np.pi * area) / (perimeter ** 2)
            if circularity >= min_circularity:
                (x, y), radius = cv2.minEnclosingCircle(contour)
                if min_radius <= radius <= max_radius:
                    candidates.append((float(x), float(y), float(radius), float(area)))

        before = len(contours)
        after = len(candidates)
        rejected = before - after
        logger.info(f"Passed: {after} / {before} contours ({rejected} rejected)")

        # Visualize passing candidates on original image
        display = img_bgra.copy()
        for (x, y, r, _) in candidates:
            cv2.circle(display, (int(round(x)), int(round(y))), int(round(r)), COLOR_GREEN, 2)
            cv2.circle(display, (int(round(x)), int(round(y))), 2, COLOR_RED, -1)

        duration = (time.perf_counter() - t0) * 1000

        result = CircularityFilterResult(
            step_id=STEP_CIRC_FILTER,
            step_label="Circularity + Radius Filter",
            success=True,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=display,
            stats={
                "Contours in": before,
                "Passed": after,
                "Rejected": rejected,
                "Min circularity": min_circularity,
                "Radius range": f"{min_radius}–{max_radius} px",
            },
            candidates_before=before,
            candidates_after=after,
            rejected=rejected,
        )
        return result, candidates

    except Exception as exc:
        duration = (time.perf_counter() - t0) * 1000
        logger.error(f"Circularity filter failed: {exc}")
        result = CircularityFilterResult(
            step_id=STEP_CIRC_FILTER,
            step_label="Circularity + Radius Filter",
            success=False,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=None,
            stats={},
            error=str(exc),
        )
        return result, []


def _deduplicate(
    circles: list,
    spatial_tol: float = 3.0,
    radius_tol: float = 3.0,
) -> list:
    """Remove circles that are within spatial_tol px of an existing one with similar radius."""
    unique: list = []
    for circle in circles:
        x, y, r, area = circle
        is_dup = False
        for ux, uy, ur, _ in unique:
            dist = np.sqrt((x - ux) ** 2 + (y - uy) ** 2)
            if dist < spatial_tol and abs(r - ur) < radius_tol:
                is_dup = True
                break
        if not is_dup:
            unique.append(circle)
    return unique


def run_deduplication(
    img_bgra: np.ndarray,
    candidates: list,
    logger: PipelineLogger,
) -> tuple[DeduplicateResult, list]:
    """Step 9 — Remove duplicate detections (close center + similar radius)."""
    t0 = time.perf_counter()
    before = len(candidates)
    logger.info(f"Deduplicating {before} candidate(s)")

    try:
        unique = _deduplicate(candidates)
        after = len(unique)
        logger.info(f"Unique after deduplication: {after} ({before - after} removed)")

        display = img_bgra.copy()
        for (x, y, r, _) in unique:
            cv2.circle(display, (int(round(x)), int(round(y))), int(round(r)), COLOR_GREEN, 2)
            cv2.circle(display, (int(round(x)), int(round(y))), 2, COLOR_RED, -1)

        duration = (time.perf_counter() - t0) * 1000

        result = DeduplicateResult(
            step_id=STEP_DEDUP,
            step_label="Deduplication",
            success=True,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=display,
            stats={"Before": before, "After": after, "Removed": before - after},
            candidates_before=before,
            candidates_after=after,
        )
        return result, unique

    except Exception as exc:
        duration = (time.perf_counter() - t0) * 1000
        logger.error(f"Deduplication failed: {exc}")
        result = DeduplicateResult(
            step_id=STEP_DEDUP,
            step_label="Deduplication",
            success=False,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=None,
            stats={},
            error=str(exc),
        )
        return result, candidates


def run_min_enclosing_filter(
    img_bgra: np.ndarray,
    candidates: list,
    area_ratio: float = 0.8,
    logger: PipelineLogger = None,
) -> tuple[MinEnclosingFilterResult, list]:
    """
    Step 10 — Filter circles where contour area is significantly smaller
    than the minimum enclosing circle area (area/enclosing_area < threshold).
    """
    t0 = time.perf_counter()
    before = len(candidates)
    if logger:
        logger.info(f"Min-enclosing area ratio filter (threshold={area_ratio}) on {before} candidate(s)")

    try:
        filtered = []
        for circle in candidates:
            x, y, r, area = circle
            enclosing_area = np.pi * (r ** 2)
            if enclosing_area > 0 and (area / enclosing_area) >= area_ratio:
                filtered.append(circle)

        after = len(filtered)
        if logger:
            logger.info(f"After min-enclosing filter: {after} ({before - after} removed)")

        display = img_bgra.copy()
        for (x, y, r, _) in filtered:
            cv2.circle(display, (int(round(x)), int(round(y))), int(round(r)), COLOR_GREEN, 2)
            cv2.circle(display, (int(round(x)), int(round(y))), 2, COLOR_RED, -1)

        duration = (time.perf_counter() - t0) * 1000
        logs = logger.get_lines() if logger else []

        result = MinEnclosingFilterResult(
            step_id=STEP_MIN_ENCLOSING,
            step_label="Min-Enclosing Circle Filter",
            success=True,
            duration_ms=duration,
            logs=logs,
            image=display,
            stats={"Before": before, "After": after, "Removed": before - after},
            candidates_before=before,
            candidates_after=after,
        )
        return result, filtered

    except Exception as exc:
        duration = (time.perf_counter() - t0) * 1000
        logs = logger.get_lines() if logger else []
        if logger:
            logger.error(f"Min-enclosing filter failed: {exc}")
        result = MinEnclosingFilterResult(
            step_id=STEP_MIN_ENCLOSING,
            step_label="Min-Enclosing Circle Filter",
            success=False,
            duration_ms=duration,
            logs=logs,
            image=None,
            stats={},
            error=str(exc),
        )
        return result, candidates


def run_inner_circle_pick(
    img_bgra: np.ndarray,
    candidates: list,
    spatial_tol: float = 3.0,
    logger: PipelineLogger = None,
) -> tuple[InnerCirclePickResult, list]:
    """
    Step 11 — For overlapping circles (same center), keep the one with the smaller radius.
    """
    t0 = time.perf_counter()
    before = len(candidates)
    if logger:
        logger.info(f"Inner circle pick on {before} candidate(s)")

    try:
        unique: list = []
        for circle in candidates:
            x, y, r, area = circle
            replaced = False
            for i, (ux, uy, ur, _) in enumerate(unique):
                dist = np.sqrt((x - ux) ** 2 + (y - uy) ** 2)
                if dist < spatial_tol:
                    if r < ur:
                        unique[i] = circle
                    replaced = True
                    break
            if not replaced:
                unique.append(circle)

        after = len(unique)
        if logger:
            logger.info(f"After inner circle pick: {after} ({before - after} removed)")

        display = img_bgra.copy()
        for (x, y, r, _) in unique:
            cv2.circle(display, (int(round(x)), int(round(y))), int(round(r)), COLOR_GREEN, 2)
            cv2.circle(display, (int(round(x)), int(round(y))), 2, COLOR_RED, -1)

        duration = (time.perf_counter() - t0) * 1000
        logs = logger.get_lines() if logger else []

        result = InnerCirclePickResult(
            step_id=STEP_INNER_PICK,
            step_label="Inner Circle Pick",
            success=True,
            duration_ms=duration,
            logs=logs,
            image=display,
            stats={"Before": before, "After": after, "Removed": before - after},
            candidates_before=before,
            candidates_after=after,
        )
        return result, unique

    except Exception as exc:
        duration = (time.perf_counter() - t0) * 1000
        logs = logger.get_lines() if logger else []
        result = InnerCirclePickResult(
            step_id=STEP_INNER_PICK,
            step_label="Inner Circle Pick",
            success=False,
            duration_ms=duration,
            logs=logs,
            image=None,
            stats={},
            error=str(exc),
        )
        return result, candidates


def run_proximity_filter(
    img_bgra: np.ndarray,
    candidates: list,
    proximity_tolerance: int = PROXIMITY_TOLERANCE,
    logger: PipelineLogger = None,
) -> tuple[ProximityFilterResult, list]:
    """
    Step 12 — Filter circles that are too close to each other along the same axis.
    Removes both circles when they share a nearly-equal X or Y coordinate
    and are within proximity_tolerance px of each other (connector pin rejection).
    """
    t0 = time.perf_counter()
    before = len(candidates)
    if logger:
        logger.info(f"Proximity filter (tolerance={proximity_tolerance} px) on {before} candidate(s)")

    try:
        to_filter = [False] * before
        for i in range(before):
            for j in range(i + 1, before):
                x1, y1, r1, _ = candidates[i]
                x2, y2, r2, _ = candidates[j]
                # Same Y row, close X spacing
                if abs(y1 - y2) < 5.0 and abs(x1 - x2) < proximity_tolerance:
                    to_filter[i] = True
                    to_filter[j] = True
                # Same X column, close Y spacing
                if abs(x1 - x2) < 5.0 and abs(y1 - y2) < proximity_tolerance:
                    to_filter[i] = True
                    to_filter[j] = True

        filtered = [c for k, c in enumerate(candidates) if not to_filter[k]]
        after = len(filtered)
        if logger:
            logger.info(f"After proximity filter: {after} ({before - after} removed)")

        display = img_bgra.copy()
        for (x, y, r, _) in filtered:
            cv2.circle(display, (int(round(x)), int(round(y))), int(round(r)), COLOR_GREEN, 2)
            cv2.circle(display, (int(round(x)), int(round(y))), 2, COLOR_RED, -1)

        duration = (time.perf_counter() - t0) * 1000
        logs = logger.get_lines() if logger else []

        result = ProximityFilterResult(
            step_id=STEP_PROXIMITY,
            step_label="Proximity Filter",
            success=True,
            duration_ms=duration,
            logs=logs,
            image=display,
            stats={"Before": before, "After": after, "Removed": before - after,
                   "Tolerance": f"{proximity_tolerance} px"},
            candidates_before=before,
            candidates_after=after,
        )
        return result, filtered

    except Exception as exc:
        duration = (time.perf_counter() - t0) * 1000
        logs = logger.get_lines() if logger else []
        result = ProximityFilterResult(
            step_id=STEP_PROXIMITY,
            step_label="Proximity Filter",
            success=False,
            duration_ms=duration,
            logs=logs,
            image=None,
            stats={},
            error=str(exc),
        )
        return result, candidates


def run_annotate_and_export(
    img_bgra: np.ndarray,
    candidates: list,
    stem: str,
    output_dir: Path,
    logger: PipelineLogger,
) -> AnnotateResult:
    """
    Step 13 — Annotate the final image with detected circles and export JSON metadata.
    """
    t0 = time.perf_counter()
    count = len(candidates)
    logger.info(f"Annotating {count} fiducial candidate(s)")

    try:
        display = img_bgra.copy()

        # Build fiducial JSON data
        fiducials_data = []
        for idx, (x, y, r, area) in enumerate(candidates, start=1):
            cx_i, cy_i, cr_i = int(round(x)), int(round(y)), int(round(r))

            # Draw boundary circle (green), center dot (red), ID label (blue)
            cv2.circle(display, (cx_i, cy_i), cr_i, COLOR_GREEN, 2)
            cv2.circle(display, (cx_i, cy_i), 2, COLOR_RED, -1)
            cv2.putText(
                display,
                f"ID:{idx}",
                (cx_i + 10, cy_i - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                COLOR_BLUE,
                1,
                cv2.LINE_AA,
            )
            logger.info(f"  Candidate {idx}: center=({cx_i},{cy_i}), r={cr_i}")

            fiducials_data.append({
                "fid_candidate_id": idx,
                "center_x": round(float(x), 3),
                "center_y": round(float(y), 3),
                "radius_px": round(float(r), 3),
            })

        # Write JSON
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / f"{stem}_fiducial_candidates.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(fiducials_data, f, indent=4)
        logger.info(f"JSON written: {json_path.name}")

        duration = (time.perf_counter() - t0) * 1000

        return AnnotateResult(
            step_id=STEP_ANNOTATE,
            step_label="Annotate + Export JSON",
            success=True,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=display,
            stats={"Detected fiducials": count, "JSON": json_path.name},
            detected_count=count,
            json_path=json_path,
        )

    except Exception as exc:
        duration = (time.perf_counter() - t0) * 1000
        logger.error(f"Annotation failed: {exc}")
        return AnnotateResult(
            step_id=STEP_ANNOTATE,
            step_label="Annotate + Export JSON",
            success=False,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=None,
            stats={},
            error=str(exc),
        )
