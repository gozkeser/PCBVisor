#!/usr/bin/env python3
"""
Fiducial Display Utility
Loads a PNG image, maps real-world fiducial coordinates directly from the
JSON file (utilizing matrix, origin, and pre-matched fiducials), and draws
annotated markers for the origin and fiducials.

Usage:
    python fid_display.py -i 3D_TOP_expanded.png -j 3D_TOP_expanded_fiducial_candidates_origin.json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

AUTHOR = "G.OZKESER"
VERSION = "1.03"
LAST_UPDATE_DATE = "12.07.2026"

# =================================================================
# MARKER & DISPLAY CONFIGURATION (PARAMETRIC)
# =================================================================
# Real-world fiducial radius in mm to calculate pixel radius R dynamically if needed:
REAL_FIDUCIAL_RADIUS_MM = 0.5  

# Prevent overlay markers from touching or obscuring the physical pad image
# This offset is added directly to the detected fiducial radius
FIDUCIAL_RADIUS_OFFSET_PX = 10   # px

# Styling for fiducials (BGRA format to support transparency overlays)
LINE_THICKNESS = 3              # px
COLOR_FIDUCIAL = (0, 255, 0, 255) # Green, fully opaque
MARKER_SIZE_MULTIPLIER = 3.0    # Scale factor for shape size (e.g. 2R, 3R)

# Shape style: 'circle', 'concentric', 'reticle', 'target'
MARKER_SHAPE = 'reticle'

# Styling for origin (BGRA format)
COLOR_ORIGIN = (255, 255, 255, 255) # White, fully opaque
ORIGIN_MARKER_SIZE = 40         # px

# Labels configuration
SHOW_LABELS = True
SHOW_COORDINATES = False
TEXT_FONT = cv2.FONT_HERSHEY_SIMPLEX
TEXT_SCALE = 1
TEXT_THICKNESS = 2
COLOR_TEXT = (255, 255, 255, 255)  # White, fully opaque

# Bounding box mapping for layer detection
FILENAME_LAYER_MAP: dict[str, str] = {
    "BOTTOM": "BottomLayer",
    "BOT": "BottomLayer",
    "TOP": "TopLayer",
}


def detect_layer_from_filename(filepath: Path) -> Optional[str]:
    """Infer layer (BottomLayer/TopLayer) from filename substring."""
    stem_upper = filepath.stem.upper()
    for key, layer in FILENAME_LAYER_MAP.items():
        if key in stem_upper:
            return layer
    return None


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
    """Draw a coordinate origin marker on the image mapped to real-world directions."""
    cx, cy = center
    size = ORIGIN_MARKER_SIZE
    L = size * 2
    
    # Draw center dot and main circle boundary
    cv2.circle(img, (cx, cy), 5, COLOR_ORIGIN, -1)
    cv2.circle(img, (cx, cy), size, COLOR_ORIGIN, LINE_THICKNESS)
    
    # Project unit vectors of X and Y axes
    # M columns 0 and 1 represent X and Y directions in pixel space.
    dx_x = (M[0, 0] / scale) * L
    dy_x = (M[1, 0] / scale) * L
    
    dx_y = (M[0, 1] / scale) * L
    dy_y = (M[1, 1] / scale) * L

    target_x = (int(round(cx + dx_x)), int(round(cy + dy_x)))
    target_y = (int(round(cx + dx_y)), int(round(cy + dy_y)))

    # Draw X-axis direction arrow
    cv2.arrowedLine(img, (cx, cy), target_x, COLOR_ORIGIN, LINE_THICKNESS, tipLength=0.15)
    cv2.putText(img, "X", (target_x[0] + (10 if dx_x >= 0 else -15), target_x[1] + (5 if dy_x >= 0 else -5)), 
                TEXT_FONT, TEXT_SCALE, COLOR_ORIGIN, TEXT_THICKNESS)
    
    # Draw Y-axis direction arrow
    cv2.arrowedLine(img, (cx, cy), target_y, COLOR_ORIGIN, LINE_THICKNESS, tipLength=0.15)
    cv2.putText(img, "Y", (target_y[0] + (10 if dx_y >= 0 else -15), target_y[1] + (5 if dy_y >= 0 else -5)), 
                TEXT_FONT, TEXT_SCALE, COLOR_ORIGIN, TEXT_THICKNESS)
    
    # Overlay the label for origin coordinates
    cv2.putText(img, "ORIGIN (0,0)", (cx + 25, cy - 25), TEXT_FONT, TEXT_SCALE, COLOR_ORIGIN, TEXT_THICKNESS + 1)


def main():
    print("=================================================================")
    print(f"    Fiducial Display Utility Version: {VERSION}")
    print("=================================================================")

    parser = argparse.ArgumentParser(description="Draws fiducials and origin on PNG image.")
    parser.add_argument("-i", "--image", required=True, help="Input PNG image path")
    parser.add_argument("-j", "--json", required=True, help="Input JSON file containing matrix and fiducials")
    parser.add_argument("-l", "--layer", help="Target layer (auto-detected if omitted)")
    parser.add_argument("-o", "--output", help="Output annotated PNG path")

    args = parser.parse_args()

    image_path = Path(args.image)
    json_path = Path(args.json)

    # 1. Load transformation matrix, origin, and fiducials from JSON file
    print(f"[*] Loading data from: {json_path.name}")
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            json_data = json.load(f)
        M = np.array(json_data["transformation_matrix"], dtype=np.float64)
        origin_px = json_data["origin_pixel"]
        matched_fiducials = json_data.get("matched_fiducials", [])
    except Exception as e:
        print(f"[ERROR] Failed parsing JSON file: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. Detect target layer from JSON or filename
    target_layer = args.layer
    if not target_layer:
        # Check if layer is specified in JSON
        json_layer = json_data.get("layer")
        if json_layer:
            # Map shorthand to standard layer names
            if json_layer.upper() == "TOP":
                target_layer = "TopLayer"
            elif json_layer.upper() in ["BOTTOM", "BOT"]:
                target_layer = "BottomLayer"
            else:
                target_layer = json_layer
        
        # Fallback to filename deduction
        if not target_layer:
            target_layer = detect_layer_from_filename(image_path)
        if not target_layer:
            target_layer = detect_layer_from_filename(json_path)
        if not target_layer:
            target_layer = "BottomLayer"  # Fallback default
    print(f"[*] Target Layer: {target_layer}")
    print(f"    Found {len(matched_fiducials)} matched fiducial(s) in JSON")

    # Calculate scale factor S (px/mm) from transformation matrix components
    scale = float(np.sqrt(M[0, 0]**2 + M[1, 0]**2))
    print(f"    Detected scale: {scale:.4f} px/mm")

    # 3. Load input PNG image (ensuring original alpha is preserved if present)
    print(f"[*] Loading image: {image_path.name}")
    try:
        img_raw = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
    except Exception as e:
        print(f"[ERROR] Unexpected IO error loading image: {e}", file=sys.stderr)
        sys.exit(1)

    if img_raw is None:
        print(f"[ERROR] Could not load image: {image_path}", file=sys.stderr)
        sys.exit(1)
        
    # Enforce consistent 4-channel BGRA processing space
    if len(img_raw.shape) == 2:  # Grayscale image
        img = cv2.cvtColor(img_raw, cv2.COLOR_GRAY2BGRA)
    elif img_raw.shape[2] == 3:  # Opaque BGR image
        img = cv2.cvtColor(img_raw, cv2.COLOR_BGR2BGRA)
        # Apply white transparency logic (only for opaque source files)
        white_mask = (img[:, :, 0] == 255) & (img[:, :, 1] == 255) & (img[:, :, 2] == 255)
        img[white_mask, 3] = 0 
    else:  # Already 4-channel BGRA image (Native transparency preserved intact)
        img = img_raw.copy()
    
    h_img, w_img = img.shape[:2]
    print(f"    Resolution: {w_img} x {h_img} px")

    # 4. Check and expand boundary if origin lies slightly out of bounds
    orig_x, orig_y = int(round(origin_px["x"])), int(round(origin_px["y"]))

    pad_top = 0
    pad_bottom = 0
    pad_left = 0
    pad_right = 0

    # Expand boundaries by 100 pixels with transparent pixels if origin overflows
    if -100 <= orig_x < 0:
        pad_left = 100
    elif w_img <= orig_x < w_img + 100:
        pad_right = 100

    if -100 <= orig_y < 0:
        pad_top = 100
    elif h_img <= orig_y < h_img + 100:
        pad_bottom = 100

    if pad_top > 0 or pad_bottom > 0 or pad_left > 0 or pad_right > 0:
        # Pad using transparent background constant (0, 0, 0, 0)
        img = cv2.copyMakeBorder(
            img, 
            pad_top, 
            pad_bottom, 
            pad_left, 
            pad_right, 
            borderType=cv2.BORDER_CONSTANT, 
            value=[0, 0, 0, 0]
        )
        
        # Calculate updated dimensions and coordinate offset
        h_img, w_img = img.shape[:2]
        orig_x += pad_left
        orig_y += pad_top
        print(f"[*] Image boundaries expanded with transparency (Top: {pad_top}, Bottom: {pad_bottom}, Left: {pad_left}, Right: {pad_right})")

    # Draw origin on the canvas
    if 0 <= orig_x < w_img and 0 <= orig_y < h_img:
        print(f"[*] Drawing origin marker at ({orig_x}, {orig_y}) px")
        draw_origin_marker(img, (orig_x, orig_y), M, scale)
    else:
        print(f"[WARNING] Origin ({orig_x}, {orig_y}) lies outside image boundaries!")

    # 5. Draw real-world coordinate fiducials directly parsed from JSON
    print(f"[*] Drawing fiducials...")
    for rf in matched_fiducials:
        designator = rf.get("designator", "FD")
        
        # Original pixel coordinates relative to the unpadded image
        raw_x_px = rf["x_px"]
        raw_y_px = rf["y_px"]
        
        # Apply padding offset
        cx = int(round(raw_x_px)) + pad_left
        cy = int(round(raw_y_px)) + pad_top

        # Extract radius and apply parametric offset to avoid overlapping the pad image
        base_radius = rf.get("radius_px", scale * REAL_FIDUCIAL_RADIUS_MM)
        R_px = base_radius + FIDUCIAL_RADIUS_OFFSET_PX

        # Check bounds in updated frame and draw annotations
        if 0 <= cx < w_img and 0 <= cy < h_img:
            draw_fiducial_marker(img, (cx, cy), R_px)
            
            # Construct and render labels
            label_text = ""
            if SHOW_LABELS:
                label_text += designator
                
            if SHOW_COORDINATES:
                # Reconstruct real-world millimeter coordinates using inverse transform
                # Solve linear equation system: A * X = B
                A = np.array([
                    [M[0, 0], M[0, 1]],
                    [M[1, 0], M[1, 1]]
                ], dtype=np.float64)
                B = np.array([
                    raw_x_px - M[0, 2],
                    raw_y_px - M[1, 2]
                ], dtype=np.float64)
                
                try:
                    x_mm, y_mm = np.linalg.solve(A, B)
                except np.linalg.LinAlgError:
                    x_mm, y_mm = 0.0, 0.0
                    
                if label_text:
                    label_text += " "
                label_text += f"({x_mm:.1f},{y_mm:.1f})"
                
            if label_text:
                cv2.putText(img, label_text, (cx + 5, cy - 15), TEXT_FONT, TEXT_SCALE, COLOR_TEXT, TEXT_THICKNESS)
                
            print(f"    Fiducial {designator} drawn at ({cx}, {cy}) px with radius {R_px:.2f} px")
        else:
            print(f"    [!] {designator} at ({cx}, {cy}) px - outside boundaries")

    # 6. Save finalized annotated BGRA image
    output_path = args.output
    if not output_path:
        output_path = image_path.parent / f"{image_path.stem}_marked.png"
    else:
        output_path = Path(output_path)

    print(f"[*] Saving annotated image to: {output_path.name}")
    try:
        cv2.imwrite(str(output_path), img)
        print("[+] Done successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to write processed output image: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()