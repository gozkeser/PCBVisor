#!/usr/bin/env python3
"""
Fiducial Display Utility
Loads a PNG image, maps real fiducial coordinates using a transformation matrix
from the origin JSON file, and draws annotated markers for the origin and fiducials.

Usage:
    python fid_display.py -i 00000000_D01_BOT.png -c 00000000_D01_Fiducials.csv -j 00000000_D01_BOT_fiducial_candidates_origin.json
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

AUTHOR = "G.OZKESER"
VERSION = "1.00"
LAST_UPDATE_DATE = "09.07.2026"

YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
GREEN = "\033[92m"
BOLD_WHITE = "\033[1;37m"
COLOR_RESET = "\033[0m"

# =================================================================
# MARKER & DISPLAY CONFIGURATION (PARAMETRIC)
# =================================================================
# Real-world fiducial radius in mm to calculate pixel radius R dynamically:
# R = scale (px/mm) * REAL_FIDUCIAL_RADIUS_MM
REAL_FIDUCIAL_RADIUS_MM = 0.5  

# Styling for fiducials
LINE_THICKNESS = 3            # px
COLOR_FIDUCIAL = (0, 255, 0)  # Green (BGR format for OpenCV)
MARKER_SIZE_MULTIPLIER = 4.0  # Scale factor for shape size (e.g. 2R, 3R)

# Shape style: 'circle', 'concentric', 'reticle', 'target'
MARKER_SHAPE = 'reticle'

# Styling for origin
COLOR_ORIGIN = (255, 255, 255)
ORIGIN_MARKER_SIZE = 40       # px

# Labels configuration
SHOW_LABELS = True
SHOW_COORDINATES = False
TEXT_FONT = cv2.FONT_HERSHEY_SIMPLEX
TEXT_SCALE = 1
TEXT_THICKNESS = 2
COLOR_TEXT = (255, 255, 255)  # White

# Bounding box mapping for layer detection
FILENAME_LAYER_MAP: dict[str, str] = {
    "BOTTOM": "BottomLayer",
    "BOT": "BottomLayer",
    "TOP": "TopLayer",
}

COLUMN_DESIGNATOR = "Designator"
COLUMN_LAYER = "Layer"
COLUMN_CENTER_X = "Center-X(mm)"
COLUMN_CENTER_Y = "Center-Y(mm)"

FD_PREFIX_PATTERN = re.compile(r"^FD", re.IGNORECASE)


def detect_layer_from_filename(filepath: Path) -> Optional[str]:
    """Infer layer (BottomLayer/TopLayer) from filename substring."""
    stem_upper = filepath.stem.upper()
    for key, layer in FILENAME_LAYER_MAP.items():
        if key in stem_upper:
            return layer
    return None


def parse_real_fiducials(csv_path: Path, target_layer: str) -> list[dict]:
    """Parse real fiducials CSV matching the given layer."""
    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()

    header_idx = None
    header_columns = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        reader = csv.reader([stripped])
        try:
            row = next(reader)
        except StopIteration:
            continue
        row_stripped = [cell.strip().strip('"') for cell in row]
        expected_headers = {COLUMN_DESIGNATOR, COLUMN_LAYER, COLUMN_CENTER_X, COLUMN_CENTER_Y}
        if expected_headers.issubset(set(row_stripped)):
            header_idx = i
            header_columns = row_stripped
            break

    if header_idx is None:
        raise ValueError("Could not find header row in CSV file.")

    col_index: dict[str, int] = {}
    for col_name in [COLUMN_DESIGNATOR, COLUMN_LAYER, COLUMN_CENTER_X, COLUMN_CENTER_Y]:
        if col_name in header_columns:
            col_index[col_name] = header_columns.index(col_name)
        else:
            for j, hcol in enumerate(header_columns):
                if hcol.lower() == col_name.lower():
                    col_index[col_name] = j
                    break

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

        if len(row_stripped) <= max(col_index.values()):
            continue

        designator = row_stripped[col_index[COLUMN_DESIGNATOR]]
        layer = row_stripped[col_index[COLUMN_LAYER]]
        raw_x = row_stripped[col_index[COLUMN_CENTER_X]]
        raw_y = row_stripped[col_index[COLUMN_CENTER_Y]]

        if layer.strip() != target_layer:
            continue
        if not FD_PREFIX_PATTERN.match(designator.strip()):
            continue

        try:
            x_mm = float(raw_x.replace("mm", "").strip())
            y_mm = float(raw_y.replace("mm", "").strip())
        except ValueError:
            continue

        fiducials.append({
            "designator": designator.strip(),
            "x_mm": x_mm,
            "y_mm": y_mm,
        })

    return fiducials


def draw_fiducial_marker(img: np.ndarray, center: tuple[int, int], R: float):
    """Draw parametric fiducial marker on the image."""
    cx, cy = center
    r_px = int(R)
    
    if MARKER_SHAPE == 'circle':
        cv2.circle(img, (cx, cy), r_px, COLOR_FIDUCIAL, LINE_THICKNESS)
        
    elif MARKER_SHAPE == 'concentric':
        cv2.circle(img, (cx, cy), r_px, COLOR_FIDUCIAL, LINE_THICKNESS)
        cv2.circle(img, (cx, cy), int(R * MARKER_SIZE_MULTIPLIER), COLOR_FIDUCIAL, LINE_THICKNESS)
        
    elif MARKER_SHAPE == 'reticle':
        cv2.circle(img, (cx, cy), r_px, COLOR_FIDUCIAL, LINE_THICKNESS)
        L = int(R * MARKER_SIZE_MULTIPLIER)
        cv2.line(img, (cx - L, cy), (cx + L, cy), COLOR_FIDUCIAL, LINE_THICKNESS)
        cv2.line(img, (cx, cy - L), (cx, cy + L), COLOR_FIDUCIAL, LINE_THICKNESS)
        
    elif MARKER_SHAPE == 'target':
        cv2.circle(img, (cx, cy), r_px, COLOR_FIDUCIAL, LINE_THICKNESS)
        cv2.circle(img, (cx, cy), int(R * MARKER_SIZE_MULTIPLIER), COLOR_FIDUCIAL, LINE_THICKNESS)
        L = int(R * MARKER_SIZE_MULTIPLIER * 1.5)
        cv2.line(img, (cx - L, cy), (cx + L, cy), COLOR_FIDUCIAL, LINE_THICKNESS)
        cv2.line(img, (cx, cy - L), (cx, cy + L), COLOR_FIDUCIAL, LINE_THICKNESS)


def draw_origin_marker(img: np.ndarray, center: tuple[int, int], M: np.ndarray, scale: float):
    """Draw a professional coordinate origin marker on the image mapped to real-world directions."""
    cx, cy = center
    size = ORIGIN_MARKER_SIZE
    L = size * 2
    
    # Draw center dot and circle
    cv2.circle(img, (cx, cy), 5, COLOR_ORIGIN, -1)
    cv2.circle(img, (cx, cy), size, COLOR_ORIGIN, LINE_THICKNESS)
    
    # Project unit vectors of X and Y axes
    # M shape is (2, 3). Columns 0 and 1 represent X and Y directions in pixel space.
    dx_x = (M[0, 0] / scale) * L
    dy_x = (M[1, 0] / scale) * L
    
    dx_y = (M[0, 1] / scale) * L
    dy_y = (M[1, 1] / scale) * L

    target_x = (int(round(cx + dx_x)), int(round(cy + dy_x)))
    target_y = (int(round(cx + dx_y)), int(round(cy + dy_y)))

    # Draw X-axis arrow
    cv2.arrowedLine(img, (cx, cy), target_x, COLOR_ORIGIN, LINE_THICKNESS, tipLength=0.15)
    cv2.putText(img, "X", (target_x[0] + (10 if dx_x >= 0 else -15), target_x[1] + (5 if dy_x >= 0 else -5)), 
                TEXT_FONT, TEXT_SCALE, COLOR_ORIGIN, TEXT_THICKNESS)
    
    # Draw Y-axis arrow
    cv2.arrowedLine(img, (cx, cy), target_y, COLOR_ORIGIN, LINE_THICKNESS, tipLength=0.15)
    cv2.putText(img, "Y", (target_y[0] + (10 if dx_y >= 0 else -15), target_y[1] + (5 if dy_y >= 0 else -5)), 
                TEXT_FONT, TEXT_SCALE, COLOR_ORIGIN, TEXT_THICKNESS)
    
    # Label origin
    cv2.putText(img, "ORIGIN (0,0)", (cx + 25, cy - 25), TEXT_FONT, TEXT_SCALE, COLOR_ORIGIN, TEXT_THICKNESS + 1)


def main():
    print("=================================================================")
    print(f"    Fiducial Display Utility Version: {VERSION}")
    print("=================================================================")

    parser = argparse.ArgumentParser(description="Draws fiducials and origin on PNG image.")
    parser.add_argument("-i", "--image", required=True, help="Input PNG image path")
    parser.add_argument("-c", "--csv", required=True, help="Input real fiducials CSV path")
    parser.add_argument("-j", "--json", required=True, help="Input origin JSON path")
    parser.add_argument("-l", "--layer", help="Target layer (auto-detected if omitted)")
    parser.add_argument("-o", "--output", help="Output annotated PNG path")

    args = parser.parse_args()

    image_path = Path(args.image)
    csv_path = Path(args.csv)
    json_path = Path(args.json)

    # 1. Detect target layer
    target_layer = args.layer
    if not target_layer:
        target_layer = detect_layer_from_filename(image_path)
        if not target_layer:
            target_layer = detect_layer_from_filename(json_path)
        if not target_layer:
            target_layer = "BottomLayer"  # Fallback default
    print(f"[*] Target Layer: {target_layer}")

    # 2. Parse real fiducials
    print(f"[*] Parsing real coordinates from: {csv_path.name}")
    real_fids = parse_real_fiducials(csv_path, target_layer)
    print(f"    Found {len(real_fids)} real fiducial(s)")

    # 3. Load transformation matrix and origin from JSON
    print(f"[*] Loading transformation matrix from: {json_path.name}")
    with open(json_path, "r", encoding="utf-8") as f:
        origin_data = json.load(f)

    M = np.array(origin_data["transformation_matrix"], dtype=np.float64)
    origin_px = origin_data["origin_pixel"]

    # Calculate scale factor S (px/mm) from transformation matrix components
    scale = float(np.sqrt(M[0, 0]**2 + M[1, 0]**2))
    R_px = scale * REAL_FIDUCIAL_RADIUS_MM
    print(f"    Detected scale: {scale:.4f} px/mm")
    print(f"    Fiducial radius R: {R_px:.2f} px (real: {REAL_FIDUCIAL_RADIUS_MM} mm)")

    # 4. Load input PNG image
    print(f"[*] Loading image: {image_path.name}")
    img = cv2.imread(str(image_path))
    if img is None:
        print(f"{RED}[ERROR] Could not load image: {image_path}{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)
    
    h_img, w_img = img.shape[:2]
    print(f"    Resolution: {w_img} x {h_img} px")

    # 5. Draw origin
    orig_x, orig_y = int(round(origin_px["x"])), int(round(origin_px["y"]))
    if 0 <= orig_x < w_img and 0 <= orig_y < h_img:
        print(f"[*] Drawing origin marker at ({orig_x}, {orig_y}) px")
        draw_origin_marker(img, (orig_x, orig_y), M, scale)
    else:
        print(f"{YELLOW}[WARNING] Origin ({orig_x}, {orig_y}) lies outside image boundaries!{COLOR_RESET}")

    # 6. Map and draw real fiducials
    print(f"[*] Mapping and drawing fiducials...")
    for rf in real_fids:
        # Map mm coordinates using affine matrix M
        x_mm, y_mm = rf["x_mm"], rf["y_mm"]
        x_px = M[0, 0] * x_mm + M[0, 1] * y_mm + M[0, 2]
        y_px = M[1, 0] * x_mm + M[1, 1] * y_mm + M[1, 2]
        cx, cy = int(round(x_px)), int(round(y_px))

        # Check bounds before drawing
        if 0 <= cx < w_img and 0 <= cy < h_img:
            draw_fiducial_marker(img, (cx, cy), R_px)
            
            # Label drawing
            label_text = ""
            if SHOW_LABELS:
                label_text += rf["designator"]
            if SHOW_COORDINATES:
                if label_text:
                    label_text += " "
                label_text += f"({x_mm:.1f},{y_mm:.1f})"
                
            if label_text:
                cv2.putText(img, label_text, (cx + 5, cy - 15), TEXT_FONT, TEXT_SCALE, COLOR_TEXT, TEXT_THICKNESS)
                
            print(f"    Fiducial {rf['designator']} mapped to ({cx}, {cy}) px")
        else:
            print(f"    [!] {rf['designator']} mapped to ({cx}, {cy}) px - outside boundaries")

    # 7. Save output annotated image
    output_path = args.output
    if not output_path:
        output_path = image_path.parent / f"{image_path.stem}_marked.png"
    else:
        output_path = Path(output_path)

    print(f"[*] Saving annotated image to: {output_path.name}")
    cv2.imwrite(str(output_path), img)
    print(f"[+] {GREEN}Done successfully.{COLOR_RESET}")


if __name__ == "__main__":
    main()
