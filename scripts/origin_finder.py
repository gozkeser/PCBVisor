#!/usr/bin/env python3
"""
Origin Finder
Computes the pixel location of the world origin (0,0) by matching
fiducial candidate pixel coordinates (from a JSON file) with their
real-world mm coordinates (from a CSV file) using geometric transformation.

When the number of pixel candidates (M) exceeds the number of real fiducials (N),
a distance ratio filtering algorithm selects the N best-matching candidates
before performing the brute-force permutation matching.

Usage:
    python origin_finder.py -j results/00000000_D01_BOT_fiducials.json -c 00000000_D01_Fiducials.csv
    python origin_finder.py -j results/00000000_D01_BOT_fiducials.json -c 00000000_D01_Fiducials.csv --layer BottomLayer
    python origin_finder.py --version
"""

import argparse
import csv
import itertools
import json
import math
import re
import sys
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from numpy.typing import NDArray

AUTHOR = "G.OZKESER"
VERSION = "1.11"
LAST_UPDATE_DATE = "12.07.2026"

# Mapping from filename substrings to layer names.
# Longer substrings are checked first (e.g. 'BOTTOM' before 'BOT') to avoid
# premature partial matches on filenames.
FILENAME_LAYER_MAP: dict[str, str] = {
    "BOTTOM": "BottomLayer",
    "BOT": "BottomLayer",
    "TOP": "TopLayer",
}

# Column name mappings (canonical -> possible variations in CSV header)
COLUMN_DESIGNATOR = "Designator"
COLUMN_LAYER = "Layer"
COLUMN_CENTER_X = "Center-X(mm)"
COLUMN_CENTER_Y = "Center-Y(mm)"

# Match standard fiducial prefixes securely
FD_PREFIX_PATTERN = re.compile(r"^(FD|FID)", re.IGNORECASE)


def detect_layer_from_filename(filepath: Path) -> Optional[str]:
    """
    Infer the layer (BottomLayer/TopLayer) from the JSON filename stem.
    Looks for substrings like BOT, TOP, BOTTOM.
    Returns None if no matching pattern is found.
    """
    stem_upper = filepath.name.upper()
    
    # Check key mappings in order of decreasing complexity
    for key, layer in FILENAME_LAYER_MAP.items():
        if key in stem_upper:
            return layer
    return None


def parse_real_fiducials(csv_path: Path, target_layer: str) -> list[dict]:
    """
    Parse the real fiducials CSV file and return parsed target entries.
    Filters entries belonging to the specified layer and matching 'FD' prefixes.

    Handles:
    - Byte Order Mark (BOM) in files
    - Various legacy multi-byte local system encodings (e.g. UTF-8, CP1252, CP1254 Turkish, Latin-1)
    - Leading garbage lines before the main header row
    - Case-insensitive variable column ordering
    - 'mm' suffix units in coordinates
    - Double quotes escaping
    """
    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    # Try standard and local encodings sequentially to handle diverse OS output encodings gracefully
    encodings = ["utf-8-sig", "cp1252", "cp1254", "latin-1"]
    lines = None
    for enc in encodings:
        try:
            with open(csv_path, "r", encoding=enc) as f:
                lines = f.readlines()
            break
        except UnicodeDecodeError:
            continue

    if lines is None:
        # Fall back to UTF-8 with character replacement to guarantee the script never crashes
        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

    # Locate the header row containing standard expected identifiers
    header_idx = None
    header_columns = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        
        # Robust CSV parsing to capture quotes/delimiters
        reader = csv.reader([stripped])
        try:
            row = next(reader)
        except StopIteration:
            continue
        row_stripped = [cell.strip().strip('"') for cell in row]

        # All expected column markers must exist in the header row
        expected_headers = {COLUMN_DESIGNATOR, COLUMN_LAYER, COLUMN_CENTER_X, COLUMN_CENTER_Y}
        if expected_headers.issubset(set(row_stripped)):
            header_idx = i
            header_columns = row_stripped
            break

    if header_idx is None:
        raise ValueError(
            f"Could not find header row in CSV file. "
            f"Expected columns: {COLUMN_DESIGNATOR}, {COLUMN_LAYER}, "
            f"{COLUMN_CENTER_X}, {COLUMN_CENTER_Y}"
        )

    # Establish mapping from required keys to their index in the row
    col_index: dict[str, int] = {}
    for col_name in [COLUMN_DESIGNATOR, COLUMN_LAYER, COLUMN_CENTER_X, COLUMN_CENTER_Y]:
        if col_name in header_columns:
            col_index[col_name] = header_columns.index(col_name)
        else:
            found = False
            for j, hcol in enumerate(header_columns):
                if hcol.lower() == col_name.lower():
                    col_index[col_name] = j
                    found = True
                    break
            if not found:
                raise ValueError(f"Required column '{col_name}' not found in CSV header: {header_columns}")

    # Iterate through the actual data rows following the header index
    fiducials = []
    data_lines = lines[header_idx + 1:]
    for line in data_lines:
        stripped = line.strip()
        if not stripped:
            continue
        reader = csv.reader([stripped])
        try:
            row = next(reader)
        except StopIteration:
            continue
        row_stripped = [cell.strip().strip('"') for cell in row]

        # Ignore short/malformed rows
        if len(row_stripped) <= max(col_index.values()):
            continue

        designator = row_stripped[col_index[COLUMN_DESIGNATOR]]
        layer = row_stripped[col_index[COLUMN_LAYER]]
        raw_x = row_stripped[col_index[COLUMN_CENTER_X]]
        raw_y = row_stripped[col_index[COLUMN_CENTER_Y]]

        # Process only designators on the specific target layer with correct prefix
        if layer.strip() != target_layer:
            continue
        if not FD_PREFIX_PATTERN.match(designator.strip()):
            continue

        # Clean numerical properties (remove 'mm' suffix if written explicitly)
        try:
            x_mm = float(raw_x.replace("mm", "").strip())
            y_mm = float(raw_y.replace("mm", "").strip())
        except ValueError as e:
            print(f"  [!] Warning: Could not parse coordinates for '{designator}': {e}", file=sys.stderr)
            continue

        fiducials.append({
            "designator": designator.strip(),
            "x_mm": x_mm,
            "y_mm": y_mm,
        })

    if not fiducials:
        raise ValueError(
            f"No real fiducial markers (designator starting with 'FD') found for layer '{target_layer}' "
            f"in CSV file: {csv_path}"
        )

    return fiducials


def load_pixel_candidates(json_path: Path) -> list[dict]:
    """
    Load detected fiducial candidate pixel details from JSON.
    Parses 'radius' properties dynamically (supports 'radius' or 'radius_px').
    """
    if not json_path.is_file():
        raise FileNotFoundError(f"Fiducial candidates JSON file not found: {json_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list) or len(data) == 0:
        raise ValueError(f"No fiducial candidate entries found in JSON: {json_path}")

    pixel_candidates = []
    for entry in data:
        # Dynamically extract radius (checking both radius, radius_px, or fallback to 0.0)
        radius = float(entry.get("radius", entry.get("radius_px", 0.0)))
        pixel_candidates.append({
            "fid_candidate_id": entry.get("fid_candidate_id", 0),
            "x_px": float(entry["center_x"]),
            "y_px": float(entry["center_y"]),
            "radius_px": radius,
        })

    return pixel_candidates


def _compute_distance_matrix(points: NDArray[np.float32]) -> NDArray[np.float32]:
    """
    Compute pairwise Euclidean distances for a group of coordinates.
    Returns an NxN symmetric matrix.
    """
    n = len(points)
    D = np.zeros((n, n), dtype=np.float32)
    
    # Double-loop calculations optimizing through symmetry
    for i in range(n):
        for j in range(i + 1, n):
            dist = float(np.sqrt((points[i, 0] - points[j, 0]) ** 2 +
                                  (points[i, 1] - points[j, 1]) ** 2))
            D[i, j] = dist
            D[j, i] = dist
    return D


def filter_candidates_by_distance_ratio(
    pixel_candidates: list[dict],
    real_fiducials: list[dict],
    tolerance: float = 1.0
) -> list[dict]:
    """
    Filters M candidates down to N best geometry matches using distance ratio.
    """
    M = len(pixel_candidates)
    N = len(real_fiducials)

    if N < 3:
        raise ValueError(
            f"Distance ratio filtering requires at least 3 real fiducials, got {N}. "
            f"Use exact matching (M == N) instead."
        )

    if M < N:
        raise ValueError(
            f"Cannot filter: pixel candidates ({M}) < real fiducials ({N})."
        )

    print(f"[*] Filtering {M} pixel candidates -> {N} real fiducials (ratio tolerance: {tolerance})")

    # Capture real physical distances and normalize to median to build ratio invariants
    real_pts = np.array([[r["x_mm"], r["y_mm"]] for r in real_fiducials], dtype=np.float64)
    D_real = _compute_distance_matrix(real_pts)
    med_real = float(np.median(D_real[D_real > 0]))
    D_real_norm = D_real / med_real

    print(f"    Real fiducial geometry (N={N}):")
    print(f"      Pair distances (normalisation median = {med_real:.4f} mm):")
    for i in range(N):
        for j in range(i + 1, N):
            d = D_real[i, j]
            d_norm = D_real_norm[i, j]
            print(f"        {real_fiducials[i]['designator']} <-> {real_fiducials[j]['designator']}:"
                  f"  {d:8.4f} mm (norm {d_norm:.4f})")

    pixel_pts = np.array([[p["x_px"], p["y_px"]] for p in pixel_candidates], dtype=np.float64)

    # Establish baseline anchor based on the furthest real points
    max_real_dist = -1.0
    i_max, j_max = 0, 1
    for i in range(N):
        for j in range(i + 1, N):
            d = float(np.linalg.norm(real_pts[i] - real_pts[j]))
            if d > max_real_dist:
                max_real_dist = d
                i_max, j_max = i, j

    real_p1 = real_pts[i_max]
    real_p2 = real_pts[j_max]
    dx_real = real_p2[0] - real_p1[0]
    dy_real = real_p2[1] - real_p1[1]
    d2_real = dx_real**2 + dy_real**2

    # Estimate physical-to-pixel scale range boundaries
    px_min, px_max = np.min(pixel_pts, axis=0), np.max(pixel_pts, axis=0)
    real_min, real_max = np.min(real_pts, axis=0), np.max(real_pts, axis=0)
    px_diag = float(np.linalg.norm(px_max - px_min))
    real_diag = float(np.linalg.norm(real_max - real_min))
    scale_est = px_diag / max(1e-5, real_diag)
    
    min_scale = 0.75 * scale_est
    max_scale = 1.25 * scale_est

    best_rmse = float("inf")
    best_matching_indices: Optional[list[int]] = None
    best_scale = 0.0

    print(f"    [1/1] Similarity-constrained pair search (M={M}, N={N}):")
    print(f"      Base real link: {real_fiducials[i_max]['designator']} <-> {real_fiducials[j_max]['designator']} ({max_real_dist:.4f} mm)")

    # Solve matching configurations over pixel candidates (a, b) maps to (p1, p2)
    for a in range(M):
        for b in range(M):
            if a == b:
                continue
            
            dx_px = pixel_pts[b, 0] - pixel_pts[a, 0]
            dy_px = pixel_pts[b, 1] - pixel_pts[a, 1]
            d2_px = dx_px**2 + dy_px**2
            d_px = np.sqrt(d2_px)
            
            scale = d_px / max_real_dist
            if not (min_scale <= scale <= max_scale):
                continue
                
            # Iterate transform checks across regular and mirrored similarity models
            for is_reflection in [False, True]:
                if not is_reflection:
                    s_x = (dx_real * dx_px + dy_real * dy_px) / d2_real
                    s_y = (dx_real * dy_px - dy_real * dx_px) / d2_real
                    t_x = pixel_pts[a, 0] - (s_x * real_p1[0] - s_y * real_p1[1])
                    t_y = pixel_pts[a, 1] - (s_y * real_p1[0] + s_x * real_p1[1])
                    
                    projected_x = s_x * real_pts[:, 0] - s_y * real_pts[:, 1] + t_x
                    projected_y = s_y * real_pts[:, 0] + s_x * real_pts[:, 1] + t_y
                else:
                    s_x = (dx_real * dx_px - dy_real * dy_px) / d2_real
                    s_y = (dy_real * dx_px + dx_real * dy_px) / d2_real
                    t_x = pixel_pts[a, 0] - (s_x * real_p1[0] + s_y * real_p1[1])
                    t_y = pixel_pts[a, 1] - (s_y * real_p1[0] - s_x * real_p1[1])
                    
                    projected_x = s_x * real_pts[:, 0] + s_y * real_pts[:, 1] + t_x
                    projected_y = s_y * real_pts[:, 0] - s_x * real_pts[:, 1] + t_y
                    
                projected = np.column_stack((projected_x, projected_y))
                
                # Pairwise distance matrices to calculate residuals
                diffs = projected[:, np.newaxis, :] - pixel_pts[np.newaxis, :, :]
                dists = np.linalg.norm(diffs, axis=2)
                
                nearest_indices = np.argmin(dists, axis=1)
                nearest_dists = dists[np.arange(N), nearest_indices]
                
                # Bijective verification mapping
                if len(np.unique(nearest_indices)) != N:
                    continue
                    
                max_allowed_dist = max(15.0, 3.0 * scale * tolerance)
                if np.any(nearest_dists > max_allowed_dist):
                    continue
                    
                rmse = float(np.sqrt(np.mean(nearest_dists**2)))
                if rmse < best_rmse:
                    best_rmse = rmse
                    best_matching_indices = nearest_indices.tolist()
                    best_scale = scale

    if best_matching_indices is None:
        raise ValueError("Could not find candidates matching the real geometry.")

    selected = [pixel_candidates[idx] for idx in best_matching_indices]

    # Alert users if candidate geometries present geometric collinearity anomalies
    if N >= 3:
        selected_coords = np.array([[c["x_px"], c["y_px"]] for c in selected])
        centered = selected_coords - selected_coords.mean(axis=0)
        singular_values = np.linalg.svd(centered, compute_uv=False)
        min_spread = float(singular_values[1]) if len(singular_values) > 1 else 0.0
        if min_spread < 1.0:
            print(
                f"      [WARNING] Selected points are nearly collinear "
                f"(secondary singular value: {min_spread:.4f} px). "
                f"Transformation accuracy may be reduced."
            )

    print(f"      Best similarity match scale: {best_scale:.4f} px/mm, RMSE: {best_rmse:.4f} px")
    print(f"      Selected {N} candidate(s):")
    for cand in selected:
        print(f"        #{cand['fid_candidate_id']}:  ({cand['x_px']:.2f}, {cand['y_px']:.2f}) px")

    return selected


def match_fiducials_by_distance(
    pixel_candidates: list[dict],
    real_fiducials: list[dict]
) -> tuple[list[dict], list[dict], list[int]]:
    """
    Perform bijective ordering alignment using normalized distance matrices.
    Matches ordering accurately even with variable sequences across sources.
    """
    n = len(pixel_candidates)
    if n != len(real_fiducials):
        raise ValueError(
            f"Cannot match: pixel candidates ({n}) != real fiducials ({len(real_fiducials)})"
        )

    if n < 2:
        raise ValueError(f"At least 2 points needed for distance matching, got {n}")

    pixel_pts = np.array([[p["x_px"], p["y_px"]] for p in pixel_candidates], dtype=np.float32)
    real_pts = np.array([[r["x_mm"], r["y_mm"]] for r in real_fiducials], dtype=np.float32)

    D_pixel = _compute_distance_matrix(pixel_pts)
    D_real = _compute_distance_matrix(real_pts)

    med_pixel = float(np.median(D_pixel[D_pixel > 0]))
    med_real = float(np.median(D_real[D_real > 0]))

    if med_pixel == 0 or med_real == 0:
        raise ValueError("Cannot normalize distance matrices: all points are coincident")

    D_pixel_norm = D_pixel / med_pixel
    D_real_norm = D_real / med_real

    best_perm = None
    best_score = float("inf")

    indices = list(range(n))
    for perm in itertools.permutations(indices):
        D_real_perm = D_real_norm[list(perm), :][:, list(perm)]
        score = float(np.sum(np.abs(D_pixel_norm - D_real_perm)))

        if score < best_score:
            best_score = score
            best_perm = list(perm)

    if best_perm is None:
        raise ValueError("Failed to find a valid matching permutation.")

    real_list_matched = [real_fiducials[i] for i in best_perm]

    return pixel_candidates, real_list_matched, best_perm


def compute_transformation(
    pixel_points: NDArray[np.float32],
    real_points: NDArray[np.float32]
) -> tuple[NDArray[np.float32], str, float]:
    """
    Solve for translation, rotation, scale (and skew if >= 3 pts).
    """
    n_points = len(pixel_points)
    if n_points < 2:
        raise ValueError(
            f"At least 2 matching fiducial points are required for transformation. "
            f"Found: {n_points}"
        )

    if n_points == 2:
        M, inliers = cv2.estimateAffinePartial2D(
            real_points,
            pixel_points,
            method=cv2.RANSAC,
            ransacReprojThreshold=3.0
        )
        transform_type = "similarity"
    else:
        M, inliers = cv2.estimateAffine2D(
            real_points,
            pixel_points,
            method=cv2.RANSAC,
            ransacReprojThreshold=3.0
        )
        transform_type = "affine"

    if M is None:
        raise ValueError(
            "Transformation could not be computed. Points may be collinear "
            "or geometric registration RANSAC steps failed."
        )

    # Calculate Root Mean Square Error (RMSE) values on the transformation
    ones = np.ones((n_points, 1), dtype=np.float32)
    real_homogeneous = np.hstack([real_points, ones])
    projected_pixels = real_homogeneous @ M.T

    errors = projected_pixels - pixel_points
    squared_errors = errors[:, 0] ** 2 + errors[:, 1] ** 2
    rmse = float(np.sqrt(np.mean(squared_errors)))

    return M, transform_type, rmse


def compute_origin_pixel(M: NDArray[np.float32]) -> tuple[float, float]:
    """
    Evaluate the translation offset directly to yield pixel position of origin (0, 0).
    """
    origin_x = float(M[0, 2])
    origin_y = float(M[1, 2])
    return origin_x, origin_y


def build_output(
    M: NDArray[np.float32],
    origin_x: float,
    origin_y: float,
    pixel_candidates: list[dict],
    real_fiducials_matched: list[dict],
    layer: str
) -> dict:
    """
    Constructs the standard JSON output payload dictionary.
    Includes transformation matrix, integer coordinates, and newly added
    matched fiducials + layer details without breaking legacy tool schemas.
    """
    # Normalize layer name into "TOP" or "BOT"
    layer_clean = "BOT" if "BOT" in layer.upper() else "TOP"

    # Build the matched list containing designators and formatted radius parameters
    matched_list = []
    for pc, rf in zip(pixel_candidates, real_fiducials_matched):
        matched_list.append({
            "designator": rf["designator"],
            "x_px": round(float(pc["x_px"]), 2),
            "y_px": round(float(pc["y_px"]), 2),
            "radius_px": round(float(pc.get("radius_px", 0.0)), 2)
        })

    output = {
        "transformation_matrix": [
            [round(float(M[0, 0]), 6), round(float(M[0, 1]), 6), round(float(M[0, 2]), 6)],
            [round(float(M[1, 0]), 6), round(float(M[1, 1]), 6), round(float(M[1, 2]), 6)],
        ],
        "origin_pixel": {
            "x": round(origin_x),
            "y": round(origin_y),
        },
        "layer": layer_clean,
        "matched_fiducials": matched_list
    }

    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute pixel location of world origin (0,0) from fiducial marker coordinates."
    )

    parser.add_argument(
        "-j", "--json",
        type=str,
        help="Path to the fiducial candidates JSON file."
    )
    parser.add_argument(
        "-c", "--csv",
        type=str,
        help="Path to the real fiducials CSV file with world mm coordinates."
    )
    parser.add_argument(
        "-l", "--layer",
        type=str,
        default=None,
        choices=["BottomLayer", "TopLayer", "BOT", "TOP"],
        help="Layer to use (BottomLayer or TopLayer). If not specified, "
             "automatically detected from JSON filename (BOT -> BottomLayer, TOP -> TopLayer)."
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output JSON file path (default: same directory as input JSON with _origin suffix)."
    )
    parser.add_argument(
        "--ratio-tolerance",
        type=float,
        default=0.01,
        help="Normalized distance tolerance for candidate filtering (default: 0.01). "
             "Lower values = stricter matching, fewer candidates."
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"Origin Finder Version: {VERSION} (Updated: {LAST_UPDATE_DATE})",
        help="Show script version and execution details and exit."
    )

    # Manual check for argument validity if not called for version
    args = parser.parse_args()

    if not args.json or not args.csv:
        parser.print_help()
        sys.exit(1)

    json_path = Path(args.json)
    csv_path = Path(args.csv)

    # Clean and resolve layers
    if args.layer:
        layer = args.layer
        if layer == "BOT":
            layer = "BottomLayer"
        elif layer == "TOP":
            layer = "TopLayer"
    else:
        auto_layer = detect_layer_from_filename(json_path)
        if auto_layer is None:
            print(
                f"[ERROR] Could not auto-detect layer from filename '{json_path.name}'.",
                file=sys.stderr
            )
            print("  Please specify --layer (BottomLayer or TopLayer) explicitly.", file=sys.stderr)
            sys.exit(1)
        layer = auto_layer
        print(f"[*] Auto-detected layer: {layer}")

    print("=" * 65)
    print(f"    Origin Finder Version: {VERSION}")
    print("=" * 65)

    try:
        # ── Step 1: Load pixel candidates ─────────────────────────────────────
        print(f"[*] Loading pixel candidates: {json_path}")
        pixel_candidates = load_pixel_candidates(json_path)
        print(f"    Found {len(pixel_candidates)} pixel candidate(s).")

        # ── Step 2: Load real fiducials ────────────────────────────────────────
        print(f"[*] Loading real fiducials:   {csv_path} [layer: {layer}]")
        real_fiducials = parse_real_fiducials(csv_path, layer)
        N_fid = len(real_fiducials)
        print(f"    Found {N_fid} real fiducial(s):")
        for rf in real_fiducials:
            print(f"      {rf['designator']}: ({rf['x_mm']:10.4f}, {rf['y_mm']:10.4f}) mm")

        # ── Step 3: Candidate count validation & distance-ratio filtering ──────
        M = len(pixel_candidates)
        N = len(real_fiducials)

        print(f"[*] Candidate count: M={M} pixel candidates, N={N} real fiducials ", end="")

        if M < N:
            print()
            print(
                f"[ERROR] Too few pixel candidates (M={M}) for real fiducials (N={N}).",
                file=sys.stderr
            )
            print(
                f"  The number of detected candidates ({M}) must be >= "
                f"the number of FD entries in the CSV for layer '{layer}' ({N}).",
                file=sys.stderr
            )
            sys.exit(1)
        elif M == N:
            print("-> exact match, skipping distance-ratio filter")
        else:
            print("-> M > N, running distance-ratio filter")
            pixel_candidates = filter_candidates_by_distance_ratio(
                pixel_candidates, real_fiducials,
                tolerance=args.ratio_tolerance
            )
            M = len(pixel_candidates)

        if M < 2:
            print(
                f"[ERROR] At least 2 matching fiducial points are required. Found: {M}",
                file=sys.stderr
            )
            sys.exit(1)

        # ── Step 4: Permutation matching ───────────────────────────────────────
        transform_label = "similarity" if M == 2 else "affine"
        print(f"[*] Permutation matching: {M} candidates <-> {N} real fiducials ({M}! = {math.factorial(M)} permutations)")
        pixel_candidates, real_fiducials_matched, best_perm = match_fiducials_by_distance(
            pixel_candidates, real_fiducials
        )
        print(f"    Best permutation (real index order): {best_perm}")
        
        # Display matching table
        _cid = "Cand. ID"   # 8
        _px  = "Pixel X"    # 9
        _py  = "Pixel Y"    # 9
        _des = "Designator" # 10
        _rx  = "Real X"     # 11
        _ry  = "Real Y"     # 11
        _u   = "Unit"       # 4
        print(f"    Matched pairs:")
        print(f"      {_cid:>8}  {_px:>9}  {_py:>9}    {_des:>10}  {_rx:>11}  {_ry:>11}  {_u}")
        print(f"      {'-'*8}  {'-'*9}  {'-'*9}    {'-'*10}  {'-'*11}  {'-'*11}  {'-'*4}")
        for pc, rf in zip(pixel_candidates, real_fiducials_matched):
            print(f"      #{pc['fid_candidate_id']:>7d}  {pc['x_px']:>9.2f}  {pc['y_px']:>9.2f}"
                  f"    {rf['designator']:>10}  {rf['x_mm']:>11.4f}  {rf['y_mm']:>11.4f}  mm")

        # ── Step 5: Build coordinate arrays ───────────────────────────────────
        pixel_pts = np.array(
            [[pc["x_px"], pc["y_px"]] for pc in pixel_candidates],
            dtype=np.float32
        )
        real_pts = np.array(
            [[rf["x_mm"], rf["y_mm"]] for rf in real_fiducials_matched],
            dtype=np.float32
        )

        # ── Step 6: Compute transformation ────────────────────────────────────
        print(f"[*] Computing {transform_label} transformation ({M} point(s))...")
        M_mat, transform_type, rmse = compute_transformation(pixel_pts, real_pts)
        print(f"    Type: {transform_type}")
        print(f"    RMSE: {rmse:.4f} px")

        # ── Step 7: Compute and report origin ─────────────────────────────────
        origin_x, origin_y = compute_origin_pixel(M_mat)
        print(f"[+] World origin (0, 0) -> pixel: ({origin_x:.3f}, {origin_y:.3f})")

        # ── Step 8: Save output JSON ───────────────────────────────────────────
        output_data = build_output(
            M=M_mat,
            origin_x=origin_x,
            origin_y=origin_y,
            pixel_candidates=pixel_candidates,
            real_fiducials_matched=real_fiducials_matched,
            layer=layer
        )

        if args.output:
            output_path = Path(args.output)
        else:
            output_path = json_path.parent / f"{json_path.stem}_origin.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=4)

        print(f"[+] Output written to: {output_path}")
        print("[+] Done.")

    except FileNotFoundError as e:
        print(f"[ERROR] File not found: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
