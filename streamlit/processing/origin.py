"""
PCBVisor — Origin Computation Processing (Steps 14–19)

Steps:
    14. Load Pixel Candidates (from fid_finder JSON)
    15. Load Real Fiducials (from CSV)
    16. Candidate Filtering (M→N)
    17. Permutation Matching
    18. Compute Transformation
    19. Origin Export JSON

Written from scratch — does not import or call origin_finder.py.
Adds support for N=2 real fiducials (scale-constrained pair search).
"""

import csv
import itertools
import json
import math
import re
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from .logger import PipelineLogger
from .results import (
    CandidateFilterResult,
    ComputeTransformResult,
    LoadCandidatesResult,
    LoadRealFiducialsResult,
    OriginExportResult,
    PermutationMatchResult,
)

# Step IDs
STEP_LOAD_CAND = 14
STEP_LOAD_REAL = 15
STEP_FILTER = 16
STEP_MATCH = 17
STEP_TRANSFORM = 18
STEP_ORIGIN = 19

# Layer detection mapping (longest keys first to avoid prefix clashes)
FILENAME_LAYER_MAP: dict[str, str] = {
    "BOTTOM": "BottomLayer",
    "BOT": "BottomLayer",
    "TOP": "TopLayer",
}

# Fiducial designator prefix pattern
FD_PREFIX = re.compile(r"^(FD|FID)", re.IGNORECASE)

# Required CSV column names
COL_DESIGNATOR = "Designator"
COL_LAYER = "Layer"
COL_X = "Center-X(mm)"
COL_Y = "Center-Y(mm)"


# ─── Utility ─────────────────────────────────────────────────────────────────

def _detect_layer_from_filename(filename: str) -> Optional[str]:
    upper = filename.upper()
    for key, layer in FILENAME_LAYER_MAP.items():
        if key in upper:
            return layer
    return None


def _compute_distance_matrix(points: np.ndarray) -> np.ndarray:
    n = len(points)
    D = np.zeros((n, n), dtype=np.float64)
    for i in range(n):
        for j in range(i + 1, n):
            d = float(np.linalg.norm(points[i] - points[j]))
            D[i, j] = d
            D[j, i] = d
    return D


# ─── Step 14 — Load Pixel Candidates ─────────────────────────────────────────

def run_load_candidates(
    json_path: Path,
    img_bgra: Optional[np.ndarray],
    logger: PipelineLogger,
) -> tuple[LoadCandidatesResult, list[dict]]:
    """
    Step 14 — Load fiducial pixel candidates from the JSON file produced by Step 13.
    """
    t0 = time.perf_counter()
    logger.info(f"Loading pixel candidates: {json_path.name}")

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list) or len(data) == 0:
            raise ValueError("No candidate entries found in JSON")

        candidates: list[dict] = []
        for entry in data:
            radius = float(entry.get("radius", entry.get("radius_px", 0.0)))
            candidates.append({
                "fid_candidate_id": entry.get("fid_candidate_id", 0),
                "x_px": float(entry["center_x"]),
                "y_px": float(entry["center_y"]),
                "radius_px": radius,
            })

        count = len(candidates)
        logger.info(f"Loaded {count} pixel candidate(s)")

        # Visualize candidates on the image if available
        display = None
        if img_bgra is not None:
            display = img_bgra.copy()
            for c in candidates:
                cx, cy, cr = int(round(c["x_px"])), int(round(c["y_px"])), int(round(c["radius_px"]))
                cv2.circle(display, (cx, cy), max(cr, 4), (0, 255, 0, 255), 2)
                cv2.circle(display, (cx, cy), 2, (0, 0, 255, 255), -1)
                cv2.putText(display, f"#{c['fid_candidate_id']}", (cx + 5, cy - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0, 255), 1)

        duration = (time.perf_counter() - t0) * 1000
        result = LoadCandidatesResult(
            step_id=STEP_LOAD_CAND,
            step_label="Load Pixel Candidates",
            success=True,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=display,
            stats={"Pixel candidates": count},
            candidate_count=count,
        )
        return result, candidates

    except Exception as exc:
        duration = (time.perf_counter() - t0) * 1000
        logger.error(f"Failed to load candidates: {exc}")
        result = LoadCandidatesResult(
            step_id=STEP_LOAD_CAND,
            step_label="Load Pixel Candidates",
            success=False,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=None,
            stats={},
            error=str(exc),
        )
        return result, []


# ─── Step 15 — Load Real Fiducials from CSV ───────────────────────────────────

def _parse_csv_lines(csv_bytes: bytes) -> list[str]:
    """Try several encodings, return file lines."""
    for enc in ["utf-8-sig", "cp1252", "cp1254", "latin-1"]:
        try:
            return csv_bytes.decode(enc).splitlines()
        except (UnicodeDecodeError, AttributeError):
            continue
    return csv_bytes.decode("utf-8", errors="replace").splitlines()


def _normalize_layer_name(layer_str: str) -> str:
    l_up = layer_str.strip().upper()
    if "BOT" in l_up:
        return "BottomLayer"
    if "TOP" in l_up:
        return "TopLayer"
    return layer_str.strip()


def run_load_real_fiducials(
    csv_bytes: bytes,
    csv_filename: str,
    image_filename: str,
    layer: Optional[str],
    logger: PipelineLogger,
) -> tuple[LoadRealFiducialsResult, list[dict], str]:
    """
    Step 15 — Parse PPL CSV and extract real fiducial coordinates for the target layer.
    Columns are matched by name (order-independent). Leading metadata rows are skipped.
    Returns (result, real_fiducials, resolved_layer).
    """
    t0 = time.perf_counter()

    # Resolve layer from image filename (or CSV fallback)
    if not layer or layer == "auto":
        detected = _detect_layer_from_filename(image_filename) or _detect_layer_from_filename(csv_filename)
        resolved_layer = detected or "TopLayer"
        logger.info(f"Auto-detected layer: '{resolved_layer}' from image '{image_filename}'")
    else:
        resolved_layer = _normalize_layer_name(layer)
        logger.info(f"Using specified layer: '{resolved_layer}'")

    logger.info(f"Parsing CSV: {csv_filename} for layer '{resolved_layer}'")

    try:
        lines = _parse_csv_lines(csv_bytes)

        # Find header row
        required = {COL_DESIGNATOR, COL_LAYER, COL_X, COL_Y}
        header_idx: Optional[int] = None
        header_cols: list[str] = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            reader = csv.reader([stripped])
            try:
                row = next(reader)
            except StopIteration:
                continue
            row_clean = [c.strip().strip('"') for c in row]
            if required.issubset(set(row_clean)):
                header_idx = i
                header_cols = row_clean
                break

        if header_idx is None:
            raise ValueError(
                f"Could not find CSV header row. Required columns: {required}"
            )

        logger.info(f"Header found at line {header_idx + 1}")

        # Map column names → indices (case-insensitive fallback)
        col_idx: dict[str, int] = {}
        for col in [COL_DESIGNATOR, COL_LAYER, COL_X, COL_Y]:
            if col in header_cols:
                col_idx[col] = header_cols.index(col)
            else:
                for j, hc in enumerate(header_cols):
                    if hc.lower() == col.lower():
                        col_idx[col] = j
                        break
                else:
                    raise ValueError(f"Required column '{col}' not found in header")

        # Parse data rows
        fiducials: list[dict] = []
        for line in lines[header_idx + 1:]:
            stripped = line.strip()
            if not stripped:
                continue
            reader = csv.reader([stripped])
            try:
                row = next(reader)
            except StopIteration:
                continue
            row_clean = [c.strip().strip('"') for c in row]
            if len(row_clean) <= max(col_idx.values()):
                continue

            designator = row_clean[col_idx[COL_DESIGNATOR]]
            row_layer = row_clean[col_idx[COL_LAYER]]
            raw_x = row_clean[col_idx[COL_X]]
            raw_y = row_clean[col_idx[COL_Y]]

            norm_row_layer = _normalize_layer_name(row_layer)
            if norm_row_layer.lower() != resolved_layer.lower():
                continue
            if not FD_PREFIX.match(designator.strip()):
                continue

            try:
                x_mm = float(raw_x.replace("mm", "").strip())
                y_mm = float(raw_y.replace("mm", "").strip())
            except ValueError as e:
                logger.warning(f"Skipping '{designator}': bad coordinates ({e})")
                continue

            fiducials.append({
                "designator": designator.strip(),
                "x_mm": x_mm,
                "y_mm": y_mm,
            })

        if not fiducials:
            raise ValueError(
                f"No fiducials (FD/FID prefix) found for layer '{resolved_layer}' in CSV"
            )

        count = len(fiducials)
        logger.info(f"Loaded {count} real fiducial(s):")
        for fid in fiducials:
            logger.info(f"  {fid['designator']}: ({fid['x_mm']:.4f}, {fid['y_mm']:.4f}) mm")

        duration = (time.perf_counter() - t0) * 1000
        result = LoadRealFiducialsResult(
            step_id=STEP_LOAD_REAL,
            step_label="Load Real Fiducials",
            success=True,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=None,
            stats={"Real fiducials": count, "Layer": resolved_layer},
            fiducial_count=count,
            layer=resolved_layer,
        )
        return result, fiducials, resolved_layer

    except Exception as exc:
        duration = (time.perf_counter() - t0) * 1000
        logger.error(f"Failed to load real fiducials: {exc}")
        result = LoadRealFiducialsResult(
            step_id=STEP_LOAD_REAL,
            step_label="Load Real Fiducials",
            success=False,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=None,
            stats={},
            error=str(exc),
        )
        return result, [], resolved_layer if 'resolved_layer' in locals() else ""


# ─── Step 16 — Candidate Filtering ────────────────────────────────────────────

def _filter_n2(
    pixel_candidates: list[dict],
    real_fiducials: list[dict],
    logger: PipelineLogger,
) -> list[dict]:
    """
    Scale-constrained pair search for N=2 real fiducials.
    For every ordered pair (a,b) of pixel candidates, compute pixel distance.
    Accept the pair whose scale (d_px / d_mm) is closest to the global scale estimate.
    """
    real_pts = np.array([[r["x_mm"], r["y_mm"]] for r in real_fiducials])
    d_mm = float(np.linalg.norm(real_pts[0] - real_pts[1]))
    if d_mm < 1e-6:
        raise ValueError("Real fiducials are coincident — cannot compute scale")

    pixel_pts = np.array([[p["x_px"], p["y_px"]] for p in pixel_candidates])
    M = len(pixel_candidates)

    # Global scale estimate from bounding boxes
    px_diag = float(np.linalg.norm(pixel_pts.max(axis=0) - pixel_pts.min(axis=0)))
    real_diag = float(np.linalg.norm(real_pts.max(axis=0) - real_pts.min(axis=0)))
    scale_est = px_diag / max(1e-5, real_diag)
    min_scale = 0.75 * scale_est
    max_scale = 1.25 * scale_est

    logger.info(f"N=2 pair search: d_mm={d_mm:.4f}, scale_est={scale_est:.3f} px/mm "
                f"[{min_scale:.3f}–{max_scale:.3f}]")

    best_scale_err = float("inf")
    best_pair: Optional[tuple[int, int]] = None

    for a in range(M):
        for b in range(M):
            if a == b:
                continue
            d_px = float(np.linalg.norm(pixel_pts[a] - pixel_pts[b]))
            scale = d_px / d_mm
            if min_scale <= scale <= max_scale:
                err = abs(scale - scale_est)
                if err < best_scale_err:
                    best_scale_err = err
                    best_pair = (a, b)

    if best_pair is None:
        raise ValueError(
            "No pixel pair found within the expected scale range for 2-fiducial matching"
        )

    a, b = best_pair
    selected = [pixel_candidates[a], pixel_candidates[b]]
    logger.info(f"Selected pair: #{pixel_candidates[a]['fid_candidate_id']} and "
                f"#{pixel_candidates[b]['fid_candidate_id']}")
    return selected


def _filter_n3plus(
    pixel_candidates: list[dict],
    real_fiducials: list[dict],
    tolerance: float,
    logger: PipelineLogger,
) -> list[dict]:
    """
    Median-normalized distance ratio filtering for N >= 3.
    Mirrors the algorithm in origin_finder.py::filter_candidates_by_distance_ratio.
    """
    M = len(pixel_candidates)
    N = len(real_fiducials)

    real_pts = np.array([[r["x_mm"], r["y_mm"]] for r in real_fiducials], dtype=np.float64)
    D_real = _compute_distance_matrix(real_pts)
    med_real = float(np.median(D_real[D_real > 0]))

    pixel_pts = np.array([[p["x_px"], p["y_px"]] for p in pixel_candidates], dtype=np.float64)

    # Find farthest real pair for anchor
    max_real_dist = -1.0
    i_max, j_max = 0, 1
    for i in range(N):
        for j in range(i + 1, N):
            d = float(np.linalg.norm(real_pts[i] - real_pts[j]))
            if d > max_real_dist:
                max_real_dist = d
                i_max, j_max = i, j

    real_p1, real_p2 = real_pts[i_max], real_pts[j_max]
    dx_real = real_p2[0] - real_p1[0]
    dy_real = real_p2[1] - real_p1[1]
    d2_real = dx_real ** 2 + dy_real ** 2

    px_diag = float(np.linalg.norm(pixel_pts.max(axis=0) - pixel_pts.min(axis=0)))
    real_diag = float(np.linalg.norm(real_pts.max(axis=0) - real_pts.min(axis=0)))
    scale_est = px_diag / max(1e-5, real_diag)
    min_scale, max_scale = 0.75 * scale_est, 1.25 * scale_est

    best_rmse = float("inf")
    best_indices: Optional[list[int]] = None

    for a in range(M):
        for b in range(M):
            if a == b:
                continue
            dx_px = pixel_pts[b, 0] - pixel_pts[a, 0]
            dy_px = pixel_pts[b, 1] - pixel_pts[a, 1]
            d2_px = dx_px ** 2 + dy_px ** 2
            d_px = np.sqrt(d2_px)
            scale = d_px / max_real_dist
            if not (min_scale <= scale <= max_scale):
                continue
            for reflect in [False, True]:
                if not reflect:
                    s_x = (dx_real * dx_px + dy_real * dy_px) / d2_real
                    s_y = (dx_real * dy_px - dy_real * dx_px) / d2_real
                    t_x = pixel_pts[a, 0] - (s_x * real_p1[0] - s_y * real_p1[1])
                    t_y = pixel_pts[a, 1] - (s_y * real_p1[0] + s_x * real_p1[1])
                    proj_x = s_x * real_pts[:, 0] - s_y * real_pts[:, 1] + t_x
                    proj_y = s_y * real_pts[:, 0] + s_x * real_pts[:, 1] + t_y
                else:
                    s_x = (dx_real * dx_px - dy_real * dy_px) / d2_real
                    s_y = (dy_real * dx_px + dx_real * dy_px) / d2_real
                    t_x = pixel_pts[a, 0] - (s_x * real_p1[0] + s_y * real_p1[1])
                    t_y = pixel_pts[a, 1] - (s_y * real_p1[0] - s_x * real_p1[1])
                    proj_x = s_x * real_pts[:, 0] + s_y * real_pts[:, 1] + t_x
                    proj_y = s_y * real_pts[:, 0] - s_x * real_pts[:, 1] + t_y

                projected = np.column_stack((proj_x, proj_y))
                diffs = projected[:, np.newaxis, :] - pixel_pts[np.newaxis, :, :]
                dists = np.linalg.norm(diffs, axis=2)
                nearest = np.argmin(dists, axis=1)
                nearest_dists = dists[np.arange(N), nearest]

                if len(np.unique(nearest)) != N:
                    continue
                max_allowed = max(15.0, 3.0 * scale * tolerance)
                if np.any(nearest_dists > max_allowed):
                    continue

                rmse = float(np.sqrt(np.mean(nearest_dists ** 2)))
                if rmse < best_rmse:
                    best_rmse = rmse
                    best_indices = nearest.tolist()

    if best_indices is None:
        raise ValueError("Could not find candidates matching the real fiducial geometry")

    return [pixel_candidates[idx] for idx in best_indices]


def run_candidate_filter(
    img_bgra: Optional[np.ndarray],
    pixel_candidates: list[dict],
    real_fiducials: list[dict],
    ratio_tolerance: float,
    logger: PipelineLogger,
) -> tuple[CandidateFilterResult, list[dict]]:
    """
    Step 16 — Reduce M pixel candidates to N matching the real fiducials.

    N == M: skip (exact match)
    N == 2: scale-constrained pair search (new 2-fiducial support)
    N >= 3: median-normalized distance ratio filtering
    """
    t0 = time.perf_counter()
    M = len(pixel_candidates)
    N = len(real_fiducials)
    logger.info(f"Candidate filtering: M={M} pixel candidates, N={N} real fiducials")

    try:
        if M < N:
            raise ValueError(
                f"Too few pixel candidates (M={M}) for real fiducials (N={N}). "
                f"Detected candidates must be >= number of fiducials in the CSV."
            )

        if M == N:
            logger.info("Exact match (M==N) — skipping distance-ratio filter")
            selected = pixel_candidates
            algorithm = "exact_match"
            scale = 0.0
        elif N == 2:
            logger.info("N=2 — using scale-constrained pair search")
            selected = _filter_n2(pixel_candidates, real_fiducials, logger)
            algorithm = "scale_pair_search"
            real_pts = np.array([[r["x_mm"], r["y_mm"]] for r in real_fiducials])
            d_mm = float(np.linalg.norm(real_pts[0] - real_pts[1]))
            sel_pts = np.array([[s["x_px"], s["y_px"]] for s in selected])
            d_px = float(np.linalg.norm(sel_pts[0] - sel_pts[1]))
            scale = d_px / d_mm if d_mm > 0 else 0.0
        else:
            logger.info(f"N={N} >= 3 — using distance-ratio filtering")
            selected = _filter_n3plus(pixel_candidates, real_fiducials, ratio_tolerance, logger)
            algorithm = "distance_ratio"
            scale = 0.0

        logger.info(f"Selected {len(selected)} candidate(s) using {algorithm}")

        display = None
        if img_bgra is not None:
            display = img_bgra.copy()
            for c in selected:
                cx, cy, cr = int(round(c["x_px"])), int(round(c["y_px"])), int(round(c["radius_px"]))
                cv2.circle(display, (cx, cy), max(cr, 4), (0, 255, 255, 255), 3)
                cv2.circle(display, (cx, cy), 2, (0, 0, 255, 255), -1)

        duration = (time.perf_counter() - t0) * 1000
        result = CandidateFilterResult(
            step_id=STEP_FILTER,
            step_label="Candidate Filtering",
            success=True,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=display,
            stats={"Algorithm": algorithm, "M in": M, "N target": N, "Selected": len(selected)},
            algorithm=algorithm,
            m_before=M,
            n_target=N,
            scale_px_per_mm=scale,
        )
        return result, selected

    except Exception as exc:
        duration = (time.perf_counter() - t0) * 1000
        logger.error(f"Candidate filtering failed: {exc}")
        result = CandidateFilterResult(
            step_id=STEP_FILTER,
            step_label="Candidate Filtering",
            success=False,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=None,
            stats={},
            error=str(exc),
        )
        return result, pixel_candidates


# ─── Step 17 — Permutation Matching ──────────────────────────────────────────

def run_permutation_match(
    img_bgra: Optional[np.ndarray],
    pixel_candidates: list[dict],
    real_fiducials: list[dict],
    logger: PipelineLogger,
) -> tuple[PermutationMatchResult, list[dict], list[dict]]:
    """
    Step 17 — Find the best bijective ordering of pixel candidates → real fiducials
    using normalized distance matrix comparison over all permutations.
    Returns (result, ordered_pixel_candidates, ordered_real_fiducials).
    """
    t0 = time.perf_counter()
    n = len(pixel_candidates)
    logger.info(f"Permutation matching: {n}! = {math.factorial(n)} permutations")

    try:
        if n != len(real_fiducials):
            raise ValueError(
                f"Count mismatch after filtering: {n} pixel != {len(real_fiducials)} real"
            )
        if n < 2:
            raise ValueError(f"Need at least 2 matched points, got {n}")

        pixel_pts = np.array([[p["x_px"], p["y_px"]] for p in pixel_candidates], dtype=np.float32)
        real_pts = np.array([[r["x_mm"], r["y_mm"]] for r in real_fiducials], dtype=np.float32)

        D_px = _compute_distance_matrix(pixel_pts.astype(np.float64))
        D_real = _compute_distance_matrix(real_pts.astype(np.float64))

        med_px = float(np.median(D_px[D_px > 0])) if np.any(D_px > 0) else 1.0
        med_real = float(np.median(D_real[D_real > 0])) if np.any(D_real > 0) else 1.0

        D_px_norm = D_px / med_px
        D_real_norm = D_real / med_real

        best_perm: Optional[list[int]] = None
        best_score = float("inf")

        for perm in itertools.permutations(range(n)):
            perm_list = list(perm)
            D_real_perm = D_real_norm[perm_list, :][:, perm_list]
            score = float(np.sum(np.abs(D_px_norm - D_real_perm)))
            if score < best_score:
                best_score = score
                best_perm = perm_list

        real_matched = [real_fiducials[i] for i in best_perm]
        logger.info(f"Best permutation: {best_perm} (score={best_score:.4f})")
        for pc, rf in zip(pixel_candidates, real_matched):
            logger.info(
                f"  #{pc['fid_candidate_id']} ({pc['x_px']:.1f},{pc['y_px']:.1f})px "
                f"↔ {rf['designator']} ({rf['x_mm']:.3f},{rf['y_mm']:.3f})mm"
            )

        display = None
        if img_bgra is not None:
            display = img_bgra.copy()
            for pc, rf in zip(pixel_candidates, real_matched):
                cx, cy = int(round(pc["x_px"])), int(round(pc["y_px"]))
                cr = max(int(round(pc.get("radius_px", 8))), 4)
                cv2.circle(display, (cx, cy), cr, (0, 255, 0, 255), 2)
                cv2.putText(display, rf["designator"], (cx + 5, cy - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0, 255), 1, cv2.LINE_AA)

        duration = (time.perf_counter() - t0) * 1000
        result = PermutationMatchResult(
            step_id=STEP_MATCH,
            step_label="Permutation Matching",
            success=True,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=display,
            stats={"Permutations": math.factorial(n), "Best score": round(best_score, 4),
                   "Matched pairs": n},
            best_permutation=best_perm,
            matched_pairs=n,
        )
        return result, pixel_candidates, real_matched

    except Exception as exc:
        duration = (time.perf_counter() - t0) * 1000
        logger.error(f"Permutation matching failed: {exc}")
        result = PermutationMatchResult(
            step_id=STEP_MATCH,
            step_label="Permutation Matching",
            success=False,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=None,
            stats={},
            error=str(exc),
        )
        return result, pixel_candidates, real_fiducials


# ─── Reflection-Aware Similarity Solver ──────────────────────────────────────

def _solve_similarity_transform(
    real_pts: np.ndarray,
    pixel_pts: np.ndarray,
) -> tuple[np.ndarray, bool, float]:
    """
    Computes a 2D similarity transform mapping real_pts (mm) -> pixel_pts (px).
    Evaluates both non-reflected (is_reflection=False) and reflected (is_reflection=True).
    Returns (M_matrix, is_reflection, rmse).
    """
    real_p1, real_p2 = real_pts[0], real_pts[1]
    pixel_p1, pixel_p2 = pixel_pts[0], pixel_pts[1]

    dx_real = float(real_p2[0] - real_p1[0])
    dy_real = float(real_p2[1] - real_p1[1])
    d2_real = dx_real**2 + dy_real**2
    if d2_real < 1e-8:
        raise ValueError("Real points are coincident — cannot solve similarity transform")

    dx_px = float(pixel_p2[0] - pixel_p1[0])
    dy_px = float(pixel_p2[1] - pixel_p1[1])

    best_M: Optional[np.ndarray] = None
    best_is_reflection = False
    best_rmse = float("inf")

    for is_reflection in [False, True]:
        if not is_reflection:
            s_x = (dx_real * dx_px + dy_real * dy_px) / d2_real
            s_y = (dx_real * dy_px - dy_real * dx_px) / d2_real
            t_x = pixel_p1[0] - (s_x * real_p1[0] - s_y * real_p1[1])
            t_y = pixel_p1[1] - (s_y * real_p1[0] + s_x * real_p1[1])
            M = np.array([[s_x, -s_y, t_x], [s_y, s_x, t_y]], dtype=np.float32)
        else:
            s_x = (dx_real * dx_px - dy_real * dy_px) / d2_real
            s_y = (dy_real * dx_px + dx_real * dy_px) / d2_real
            t_x = pixel_p1[0] - (s_x * real_p1[0] + s_y * real_p1[1])
            t_y = pixel_p1[1] - (s_y * real_p1[0] - s_x * real_p1[1])
            M = np.array([[s_x, s_y, t_x], [s_y, -s_x, t_y]], dtype=np.float32)

        ones = np.ones((len(real_pts), 1), dtype=np.float32)
        real_h = np.hstack([real_pts, ones])
        proj = real_h @ M.T
        errs = proj - pixel_pts
        rmse = float(np.sqrt(np.mean(errs[:, 0]**2 + errs[:, 1]**2)))

        if rmse < best_rmse:
            best_rmse = rmse
            best_M = M
            best_is_reflection = is_reflection

    if best_M is None:
        raise ValueError("Failed to solve similarity transform")

    return best_M, best_is_reflection, best_rmse


# ─── Step 18 — Compute Transformation ────────────────────────────────────────

def run_compute_transformation(
    pixel_candidates: list[dict],
    real_fiducials_matched: list[dict],
    logger: PipelineLogger,
) -> tuple[ComputeTransformResult, Optional[np.ndarray]]:
    """
    Step 18 — Compute affine (N>=3) or similarity (N==2) transformation
    from real-world mm coordinates to pixel coordinates. Supports reflection (mirrored boards).
    Returns (result, M_matrix).
    """
    t0 = time.perf_counter()
    n = len(pixel_candidates)
    logger.info(f"Computing transformation for {n} point(s)")

    try:
        pixel_pts = np.array(
            [[p["x_px"], p["y_px"]] for p in pixel_candidates], dtype=np.float32
        )
        real_pts = np.array(
            [[r["x_mm"], r["y_mm"]] for r in real_fiducials_matched], dtype=np.float32
        )

        if n >= 3:
            M_aff, _ = cv2.estimateAffine2D(real_pts, pixel_pts, method=cv2.RANSAC,
                                             ransacReprojThreshold=3.0)
            if M_aff is not None:
                ones = np.ones((n, 1), dtype=np.float32)
                real_h = np.hstack([real_pts, ones])
                proj = real_h @ M_aff.T
                errs = proj - pixel_pts
                rmse_aff = float(np.sqrt(np.mean(errs[:, 0] ** 2 + errs[:, 1] ** 2)))
                M = M_aff
                rmse = rmse_aff
                transform_type = "affine"
            else:
                M_sim, is_refl, rmse_sim = _solve_similarity_transform(real_pts, pixel_pts)
                M = M_sim
                rmse = rmse_sim
                transform_type = "similarity (reflected)" if is_refl else "similarity"
        else:
            M_sim, is_refl, rmse_sim = _solve_similarity_transform(real_pts, pixel_pts)
            M = M_sim
            rmse = rmse_sim
            transform_type = "similarity (reflected)" if is_refl else "similarity"

        if M is None:
            raise ValueError("Transformation matrix could not be computed (RANSAC failed)")

        # Scale calculation
        scale = float(np.sqrt(M[0, 0] ** 2 + M[1, 0] ** 2))
        det = float(M[0, 0] * M[1, 1] - M[0, 1] * M[1, 0])
        is_mirrored = det < 0
        logger.info(f"Transform type: {transform_type} (det={det:.4f}, mirrored={is_mirrored})")
        logger.info(f"RMSE: {rmse:.4f} px, Scale: {scale:.4f} px/mm")

        duration = (time.perf_counter() - t0) * 1000
        result = ComputeTransformResult(
            step_id=STEP_TRANSFORM,
            step_label="Compute Transformation",
            success=True,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=None,
            stats={"Type": transform_type, "RMSE": f"{rmse:.4f} px",
                   "Scale": f"{scale:.4f} px/mm", "Mirrored": str(is_mirrored)},
            transform_type=transform_type,
            rmse_px=rmse,
            scale_px_per_mm=scale,
        )
        return result, M

    except Exception as exc:
        duration = (time.perf_counter() - t0) * 1000
        logger.error(f"Transformation computation failed: {exc}")
        result = ComputeTransformResult(
            step_id=STEP_TRANSFORM,
            step_label="Compute Transformation",
            success=False,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=None,
            stats={},
            error=str(exc),
        )
        return result, None


# ─── Step 19 — Origin Export ──────────────────────────────────────────────────

def run_origin_export(
    M: np.ndarray,
    pixel_candidates: list[dict],
    real_fiducials_matched: list[dict],
    layer: str,
    img_bgra: Optional[np.ndarray],
    output_path: Path,
    logger: PipelineLogger,
) -> OriginExportResult:
    """
    Step 19 — Extract origin pixel from transformation matrix, build JSON, write file,
    log formatted JSON payload line-by-line, and render the origin crosshair on the image.
    """
    t0 = time.perf_counter()

    try:
        origin_x = float(M[0, 2])
        origin_y = float(M[1, 2])
        logger.info(f"World origin (0,0) → pixel: ({origin_x:.3f}, {origin_y:.3f})")

        layer_clean = "BOT" if "BOT" in layer.upper() else "TOP"
        scale = float(np.sqrt(M[0, 0] ** 2 + M[1, 0] ** 2))

        matched_list = []
        for pc, rf in zip(pixel_candidates, real_fiducials_matched):
            matched_list.append({
                "designator": rf["designator"],
                "x_px": round(float(pc["x_px"]), 2),
                "y_px": round(float(pc["y_px"]), 2),
                "radius_px": round(float(pc.get("radius_px", 0.0)), 2),
            })

        output_data = {
            "transformation_matrix": [
                [round(float(M[0, 0]), 6), round(float(M[0, 1]), 6), round(float(M[0, 2]), 6)],
                [round(float(M[1, 0]), 6), round(float(M[1, 1]), 6), round(float(M[1, 2]), 6)],
            ],
            "origin_pixel": {
                "x": round(origin_x),
                "y": round(origin_y),
            },
            "layer": layer_clean,
            "matched_fiducials": matched_list,
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        json_formatted = json.dumps(output_data, indent=4)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json_formatted)

        logger.info(f"Origin JSON written to {output_path.name}:")
        for line in json_formatted.splitlines():
            logger.info(f"  {line}")

        # Visualize origin on image
        display = None
        if img_bgra is not None:
            display = img_bgra.copy()
            ox, oy = int(round(origin_x)), int(round(origin_y))
            h, w = display.shape[:2]
            if 0 <= ox < w and 0 <= oy < h:
                size = 40
                cv2.circle(display, (ox, oy), 5, (255, 255, 255, 255), -1)
                cv2.circle(display, (ox, oy), size, (255, 255, 255, 255), 2)
                L = size * 2
                # Derive axis directions from M
                dx_x = M[0, 0] / scale * L
                dy_x = M[1, 0] / scale * L
                dx_y = M[0, 1] / scale * L
                dy_y = M[1, 1] / scale * L
                tx = (int(round(ox + dx_x)), int(round(oy + dy_x)))
                ty = (int(round(ox + dx_y)), int(round(oy + dy_y)))
                cv2.arrowedLine(display, (ox, oy), tx, (255, 255, 255, 255), 2, tipLength=0.15)
                cv2.arrowedLine(display, (ox, oy), ty, (255, 255, 255, 255), 2, tipLength=0.15)
                cv2.putText(display, "X", (tx[0] + 8, tx[1] + 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255, 255), 2)
                cv2.putText(display, "Y", (ty[0] + 8, ty[1] + 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255, 255), 2)
                cv2.putText(display, "ORIGIN (0,0)", (ox + 25, oy - 25),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255, 255), 2)

        duration = (time.perf_counter() - t0) * 1000
        return OriginExportResult(
            step_id=STEP_ORIGIN,
            step_label="Origin JSON Export",
            success=True,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=display,
            stats={
                "Origin X": f"{origin_x:.1f} px",
                "Origin Y": f"{origin_y:.1f} px",
                "Layer": layer_clean,
            },
            origin_x=origin_x,
            origin_y=origin_y,
            output_path=output_path,
            json_bytes=json_formatted.encode("utf-8"),
        )

    except Exception as exc:
        duration = (time.perf_counter() - t0) * 1000
        logger.error(f"Origin export failed: {exc}")
        return OriginExportResult(
            step_id=STEP_ORIGIN,
            step_label="Origin JSON Export",
            success=False,
            duration_ms=duration,
            logs=logger.get_lines(),
            image=None,
            stats={},
            error=str(exc),
        )
