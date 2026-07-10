#!/usr/bin/env python3
"""
Circle Detector CLI Tool
Detects candidate fiducial markers in PNG images using single-pass
contour analysis and circularity filtering. Exports detected circles
as fiducial candidates to a JSON metadata file, alongside annotated
images and intermediate debug outputs.

Detection parameters are specified via optional CLI arguments.
Use --debug to generate intermediate step-by-step output files.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import re

AUTHOR = "G.OZKESER"
VERSION = "1.01"
LAST_UPDATE_DATE = "08.07.2026"

YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
GREEN = "\033[92m"
BOLD_WHITE = "\033[1;37m"
COLOR_RESET = "\033[0m"


class DualLogger:
    """Redirects stdout stream to write to both the terminal screen and a log file simultaneously."""
    ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    def __init__(self, filepath: Path) -> None:
        self.terminal = sys.stdout
        self.log_file = open(filepath, "w", encoding="utf-8")

    def write(self, message: str) -> None:
        self.terminal.write(message)
        clean_message = self.ANSI_ESCAPE.sub('', message)
        self.log_file.write(clean_message)

    def flush(self) -> None:
        self.terminal.flush()
        self.log_file.flush()

    def close(self) -> None:
        self.log_file.close()


class CircleDetector:
    """Handles image loading, preprocessing, single-pass circle detection, and output generation."""

    # Proximity tolerance for filtering close circles (pixels)
    PROXIMITY_TOLERANCE = 60

    def __init__(self, input_path: Path, output_dir: Path,
                 canny_threshold: float, min_circularity: float,
                 min_radius: int, max_radius: int,
                 debug: bool = False) -> None:
        self.input_path: Path = input_path
        self.output_dir: Path = output_dir
        self.canny_threshold: float = canny_threshold
        self.min_circularity: float = min_circularity
        self.min_radius: int = min_radius
        self.max_radius: int = max_radius
        self.debug: bool = debug
        self.detected_circles: list = []  # list of (x, y, radius)

    def _debug_path(self, step: int) -> Path:
        """Generate a debug output file path for the given step number."""
        return self.output_dir / f"{self.input_path.stem}_step{step}_out.png"

    def read_image(self) -> np.ndarray:
        """
        Reads the image from the specified input path.

        Raises:
            FileNotFoundError: If the input file is not found on the disk.
            ValueError: If the file is not a valid image format or cannot be decoded.
        """
        if not self.input_path.is_file():
            raise FileNotFoundError(f"Input file not found at: {self.input_path}")

        image: Optional[np.ndarray] = cv2.imread(str(self.input_path))
        if image is None:
            raise ValueError(f"Failed to decode or read image: {self.input_path}")

        return image

    def process_and_save_intermediates(self, image: np.ndarray) -> np.ndarray:
        """
        Converts the image to grayscale, applies a median filter, runs Canny edge detection,
        and saves intermediate outputs when debug mode is active.
        Returns the binary edge image for contour detection.
        """
        # Step 2: Convert to Grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        if self.debug:
            self._write_image(gray, self._debug_path(2))
            print(f"[DEBUG] Step 2 - Grayscale image saved to: {self._debug_path(2)}")

        # Step 3: Noise Reduction (using a 5x5 Median Blur kernel)
        blurred = cv2.medianBlur(gray, 5)

        if self.debug:
            self._write_image(blurred, self._debug_path(3))
            print(f"[DEBUG] Step 3 - Blurred image saved to: {self._debug_path(3)}")

        # Step 4: Edge Detection (using Canny Edge Detection)
        # Using canny_threshold for upper threshold, and half of it for lower threshold
        edges = cv2.Canny(blurred, self.canny_threshold / 2, self.canny_threshold)

        if self.debug:
            self._write_image(edges, self._debug_path(4))
            print(f"[DEBUG] Step 4 - Edge detection (Canny) image saved to: {self._debug_path(4)}")

        return edges

    def detect_circles(self, edge_image: np.ndarray, original_image: np.ndarray) -> list:
        """
        Performs a single-pass contour analysis to detect circular fiducial candidates.
        Filters contours by circularity and radius constraints, then deduplicates.

        Returns the list of detected circles as (x, y, radius) tuples.
        """
        # Use RETR_LIST to capture all contours
        contours, _ = cv2.findContours(edge_image, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        detected = []          # list of (x, y, radius)
        detected_info = []     # parallel list of (area, perimeter, circularity)

        print(f"[*] Analyzing {len(contours)} contour(s)...")

        for contour in contours:
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)

            # Avoid division by zero
            if perimeter == 0:
                continue

            # Compute circularity: 4 * pi * Area / Perimeter^2
            circularity = (4 * np.pi * area) / (perimeter ** 2)

            # Filter based on circularity threshold
            if circularity >= self.min_circularity:
                # Find the minimum enclosing circle for the contour
                (x, y), radius = cv2.minEnclosingCircle(contour)

                # Filter based on radius constraints
                if self.min_radius <= radius <= self.max_radius:
                    detected.append((float(x), float(y), float(radius)))
                    detected_info.append((area, perimeter, circularity))

        if detected:
            print(f"[*] Raw candidate circles before deduplication: {len(detected)}")
            if self.debug:
                print(f"\n[DEBUG] Detected Circles Summary:")
                print(f"{'ID':<6} {'Center X':<14} {'Center Y':<14} {'Radius':<10} {'Area':<14} {'Perimeter':<14} {'Circularity':<14}")
                print("-" * 90)
                for d_idx, (cx, cy, cr) in enumerate(detected):
                    area_val, perim_val, circ_val = detected_info[d_idx]
                    print(f"{d_idx:<6} {cx:<14.3f} {cy:<14.3f} {cr:<10.3f} {area_val:<14.3f} {perim_val:<14.3f} {circ_val:<14.4f}")
                print("-" * 90)

            # Deduplicate close detections
            print(f"[*] Removing duplicate circles...")
            self.detected_circles = self._deduplicate(detected)
            print(f"[*] Unique fiducial candidates after deduplication: {len(self.detected_circles)}")

            # Filter close coordinates
            print(f"[*] Filtering close coordinates...")
            before_filter = len(self.detected_circles)
            self.detected_circles = self._filter_close_coordinates(self.detected_circles)
            after_filter = len(self.detected_circles)
            print(f"[*] Fiducial candidates after coordinate filtering: {after_filter} (removed {before_filter - after_filter})")
        else:
            self.detected_circles = []
            print("[-] No circles found matching the current parameters.")

        # Save debug visualization if enabled
        if self.debug and self.detected_circles:
            debug_img = original_image.copy()
            for circle in self.detected_circles:
                cx, cy, cr = int(round(circle[0])), int(round(circle[1])), int(round(circle[2]))
                cv2.circle(debug_img, (cx, cy), cr, (0, 255, 0), 2)
                cv2.circle(debug_img, (cx, cy), 2, (0, 0, 255), -1)
            self._write_image(debug_img, self._debug_path(5))
            print(f"[DEBUG] Step 5 - Detection visualization saved to: {self._debug_path(5)}")

        return self.detected_circles

    def _deduplicate(self, circles: list, spatial_tolerance: float = 3.0, radius_tolerance: float = 3.0) -> list:
        """
        Deduplicates close detections by center proximity and radius similarity.
        """
        unique = []
        for circle in circles:
            x, y, r = circle
            is_duplicate = False
            for ux, uy, ur in unique:
                distance = np.sqrt((x - ux) ** 2 + (y - uy) ** 2)
                rad_diff = abs(r - ur)
                if distance < spatial_tolerance and rad_diff < radius_tolerance:
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique.append(circle)
        return unique

    def _filter_close_coordinates(self, circles: list) -> list:
        """
        Filters out circles that are too close to each other based on x or y coordinates.
        Circles with the same y-coordinate and x-difference < PROXIMITY_TOLERANCE are filtered.
        Circles with the same x-coordinate and y-difference < PROXIMITY_TOLERANCE are filtered.
        """
        to_filter = [False] * len(circles)
        for i in range(len(circles)):
            for j in range(i + 1, len(circles)):
                x1, y1, r1 = circles[i]
                x2, y2, r2 = circles[j]
                # Same y, close x
                if abs(y1 - y2) < 1.0 and abs(x1 - x2) < self.PROXIMITY_TOLERANCE:
                    to_filter[i] = True
                    to_filter[j] = True
                # Same x, close y
                if abs(x1 - x2) < 1.0 and abs(y1 - y2) < self.PROXIMITY_TOLERANCE:
                    to_filter[i] = True
                    to_filter[j] = True
        return [c for i, c in enumerate(circles) if not to_filter[i]]

    def save_fiducials_to_json(self) -> Path:
        """
        Exports the detected circles as fiducial candidates to a JSON file.
        """
        fiducials_data = []
        for idx, (x, y, r) in enumerate(self.detected_circles, start=1):
            fiducials_data.append({
                "fid_candidate_id": idx,
                "center_x": float(round(x, 3)),
                "center_y": float(round(y, 3)),
                "radius_px": float(round(r, 3)),
            })

        json_output_path = self.output_dir / f"{self.input_path.stem}_fiducial_candidates.json"

        try:
            with open(json_output_path, "w", encoding="utf-8") as json_file:
                json.dump(fiducials_data, json_file, indent=4)
            print(f"[+] Fiducial candidates metadata written to: {json_output_path}")
        except Exception as err:
            raise OSError(f"Failed to write JSON output file: {err}")

        return json_output_path

    def annotate_and_save(self, image: np.ndarray) -> int:
        """
        Draws detected circles, center marks, and IDs on the image.
        """
        output_path = self.output_dir / f"{self.input_path.stem}_annotated.png"

        if not self.detected_circles:
            self._write_image(image, output_path)
            print("[-] No circles detected to annotate.")
            return 0

        total = len(self.detected_circles)

        print(f"\n[+] Detected Fiducial Candidates:")
        print("-" * 60)
        print(f"{'Candidate ID':<14} {'Center':<20} {'Radius (px)':<12}")
        print("-" * 60)

        for idx, (x, y, r) in enumerate(self.detected_circles, start=1):
            coords = f"({int(round(x))}, {int(round(y))})"
            print(f"{idx:<14} {coords:<20} {int(round(r)):<12}")

            # Draw circle boundary (green)
            cv2.circle(image, (int(round(x)), int(round(y))), int(round(r)), (0, 255, 0), 2)

            # Draw center point (red)
            cv2.circle(image, (int(round(x)), int(round(y))), 2, (0, 0, 255), -1)

            # Draw ID label (blue)
            text_str = f"ID: {idx}"
            text_org = (int(round(x)) + 10, int(round(y)) - 10)
            cv2.putText(
                img=image,
                text=text_str,
                org=text_org,
                fontFace=cv2.FONT_HERSHEY_SIMPLEX,
                fontScale=0.5,
                color=(255, 0, 0),
                thickness=1,
                lineType=cv2.LINE_AA
            )

        print("-" * 60 + "\n")
        self._write_image(image, output_path)
        return total

    def _write_image(self, image: np.ndarray, path: Path) -> None:
        """
        Saves the image matrix to the specified filepath.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        success = cv2.imwrite(str(path), image)
        if not success:
            raise OSError(f"Could not write image to target path: {path}")


def main() -> None:
    """Configures CLI arguments and orchestrates circle detection execution."""

    parser = argparse.ArgumentParser(
        description="Detects circular fiducial markers in PNG images, outputting annotated visual assets and JSON metadata."
    )

    # Path Arguments
    parser.add_argument(
        "-i", "--input",
        required=True,
        type=str,
        help="Path to the input PNG image."
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=str,
        default=None,
        help="Output directory for all generated files (default: input file's directory)."
    )

    # Detection Parameters (optional — have sensible defaults)
    parser.add_argument(
        "--canny-threshold",
        type=float,
        default=100.0,
        help="Upper threshold for Canny edge detection (default: 100.0)."
    )
    parser.add_argument(
        "--min-circularity",
        type=float,
        default=0.75,
        help="Minimum circularity for circle detection (default: 0.75)."
    )
    parser.add_argument(
        "--min-radius",
        type=int,
        default=14,
        help="Minimum radius in pixels (default: 14)."
    )
    parser.add_argument(
        "--max-radius",
        type=int,
        default=18,
        help="Maximum radius in pixels (default: 18)."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode: generates intermediate step-by-step output files."
    )

    args = parser.parse_args()

    input_path = Path(args.input)

    # Verify PNG formatting constraints
    if input_path.suffix.lower() != '.png':
        print("Error: Input file must be a PNG image.", file=sys.stderr)
        sys.exit(1)

    # Determine output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = input_path.parent

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Start the log file mirroring
    log_output_path = output_dir / f"{input_path.stem}_log.txt"
    logger = DualLogger(log_output_path)
    sys.stdout = logger

    try:
        detector = CircleDetector(
            input_path=input_path,
            output_dir=output_dir,
            canny_threshold=args.canny_threshold,
            min_circularity=args.min_circularity,
            min_radius=args.min_radius,
            max_radius=args.max_radius,
            debug=args.debug
        )

        # Print active detection parameters immediately
        print("=" * 65)
        print(f"    {YELLOW}Fiducial Finder{COLOR_RESET} Version: {YELLOW}{VERSION}{COLOR_RESET} Last updated on {YELLOW}{LAST_UPDATE_DATE}{COLOR_RESET}")
        print("=" * 65)
        print("Circle Detector Pipeline - Active Configuration Parameters")
        print("=" * 65)
        print(f"[*] Input File:                 {input_path}")
        print(f"[*] Output Directory:           {output_dir}")
        print(f"[*] Output Annotated Image:     {output_dir / f'{input_path.stem}_annotated.png'}")
        print(f"[*] Output Metadata JSON:       {output_dir / f'{input_path.stem}_fiducial_candidates.json'}")
        print(f"[*] Execution Log File:         {log_output_path}")
        print(f"[*] Debug Mode:                 {'Enabled' if args.debug else 'Disabled'}")
        print(f"[*] Canny Threshold:            {args.canny_threshold}")
        print(f"[*] Min Circularity:            {args.min_circularity}")
        print(f"[*] Min Radius:                 {args.min_radius} px")
        print(f"[*] Max Radius:                 {args.max_radius} px")
        print("=" * 65)
        print("\n[*] Reading image...")
        image = detector.read_image()

        print("[*] Performing preprocessing steps...")
        edge_image = detector.process_and_save_intermediates(image)

        print("[*] Executing single-pass contour analysis...")
        circles = detector.detect_circles(edge_image, image)

        print(f"[*] Annotating results...")
        detected_count = detector.annotate_and_save(image)

        # Export fiducial candidates metadata JSON
        detector.save_fiducials_to_json()

        print(f"[+] Process completed successfully! Identified {detected_count} fiducial candidate(s) in total.")

    except FileNotFoundError as err:
        print(f"File System Error: {err}", file=sys.stderr)
        sys.exit(1)
    except ValueError as err:
        print(f"Data Validation Error: {err}", file=sys.stderr)
        sys.exit(1)
    except OSError as err:
        print(f"Write Operation Error: {err}", file=sys.stderr)
        sys.exit(1)
    except Exception as err:
        print(f"An unexpected critical error occurred: {err}", file=sys.stderr)
        sys.exit(1)
    finally:
        # Safely detach stdout mirror and close the log file
        sys.stdout = logger.terminal
        logger.close()


if __name__ == "__main__":
    main()