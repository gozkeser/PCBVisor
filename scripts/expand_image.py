#!/usr/bin/env python3
"""
Image Canvas Expander and Transparency Tool.

This script expands the canvas of an input PNG image in all directions and converts
a specified RGB color key to full transparency using OpenCV.
"""

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import cv2
import numpy as np

AUTHOR = "G.OZKESER"
VERSION = "1.00"
LAST_UPDATE_DATE = "13.07.2026"

OUTPUT_SUFFIX = "_E"

# Configure structured logging for production-level feedback
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AppConfig:
    """Read-only configuration settings for the image processing operation."""

    input_path: Path
    output_path: Path
    padding: int
    transparent_rgb: Tuple[int, int, int]


def parse_color(color_str: str) -> Tuple[int, int, int]:
    """
    Parses an RGB comma-separated string into a validated 3-tuple of integers.

    Args:
        color_str: A string representing RGB values (e.g., "254,254,254").

    Returns:
        A tuple of three integers (R, G, B) between 0 and 255.

    Raises:
        argparse.ArgumentTypeError: If the input format or values are invalid.
    """
    try:
        parts = [int(channel.strip()) for channel in color_str.split(",")]
        if len(parts) != 3:
            raise ValueError("Exactly three color channels (R, G, B) are required.")
        if not all(0 <= val <= 255 for val in parts):
            raise ValueError("Color channel values must be within the [0, 255] range.")
        return parts[0], parts[1], parts[2]
    except Exception as err:
        raise argparse.ArgumentTypeError(
            f"Invalid color format '{color_str}'. Must be 'R,G,B' (e.g., '254,254,254'). Error: {err}"
        )


def parse_arguments() -> AppConfig:
    """
    Configures and executes the command-line argument parser.

    Returns:
        An initialized AppConfig instances.
    """
    parser = argparse.ArgumentParser(
        description="Expand PNG canvas and convert a specific color to transparent."
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        type=str,
        help="Path to the input PNG image file.",
    )
    parser.add_argument(
        "-p",
        "--padding",
        type=int,
        default=125,
        help="Padding to add in pixels to all outer directions (default: %(default)s).",
    )
    parser.add_argument(
        "-c",
        "--color",
        type=parse_color,
        default="254,254,254",
        help="RGB color to convert to transparent, formatted as R,G,B (default: %(default)s).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help=f"Path to the output PNG file (default: [input_filename]{OUTPUT_SUFFIX}.png).",
    )

    args = parser.parse_args()
    input_path = Path(args.input)

    # Automatically derive the output path if it was not provided
    if args.output is None:
        output_path = input_path.with_stem(f"{input_path.stem}{OUTPUT_SUFFIX}")
    else:
        output_path = Path(args.output)

    if args.padding < 0:
        parser.error("Padding size must be a non-negative integer.")

    return AppConfig(
        input_path=input_path,
        output_path=output_path,
        padding=args.padding,
        transparent_rgb=args.color,
    )


class ImageProcessor:
    """Handles image loading, color keying, padding expansion, and export operations safely."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def process(self) -> None:
        """
        Executes the pipeline to expand the image and key the chosen transparency color.
        """
        if not self.config.input_path.exists():
            logger.error(f"Input file not found: {self.config.input_path}")
            sys.exit(1)

        # Risk-wrapped I/O: Reading the file
        try:
            logger.info(f"Loading image from: {self.config.input_path}")
            # IMREAD_UNCHANGED ensures we preserve existing alpha channels
            img = cv2.imread(str(self.config.input_path), cv2.IMREAD_UNCHANGED)
            if img is None:
                raise ValueError("The file could not be decoded as a valid image.")
        except Exception as e:
            logger.error(f"Failed to load image: {e}")
            sys.exit(1)

        # Ensure correct channel configuration (Convert to BGRA to host transparency)
        img = self._ensure_bgra(img)

        # Apply transparency keying based on the target color
        img = self._apply_color_keying(img)

        # Expand the image canvas in all directions
        img = self._expand_canvas(img)

        # Risk-wrapped I/O: Writing the file
        try:
            logger.info(f"Saving processed image to: {self.config.output_path}")
            # Ensure parent directories exist
            self.config.output_path.parent.mkdir(parents=True, exist_ok=True)
            success = cv2.imwrite(str(self.config.output_path), img)
            if not success:
                raise IOError("OpenCV write routine returned False.")
            logger.info("Processing completed successfully.")
        except Exception as e:
            logger.error(f"Failed to write output image: {e}")
            sys.exit(1)

    def _ensure_bgra(self, img: np.ndarray) -> np.ndarray:
        """Converts any grayscale or standard BGR image into a 4-channel BGRA image."""
        if len(img.shape) == 2:
            logger.info("Input image is Grayscale. Converting to BGRA...")
            return cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
        
        channels = img.shape[2]
        if channels == 3:
            logger.info("Input image is BGR. Converting to BGRA...")
            return cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
        elif channels == 4:
            return img
        else:
            raise ValueError(f"Unsupported number of image channels: {channels}")

    def _apply_color_keying(self, img: np.ndarray) -> np.ndarray:
        """Sets the Alpha channel to 0 for all pixels matching the specified RGB key."""
        r, g, b = self.config.transparent_rgb
        logger.info(f"Applying transparency filter to RGB color ({r}, {g}, {b})...")

        # OpenCV reads channels in BGR order
        target_bgr = np.array([b, g, r], dtype=np.uint8)

        # Create a boolean mask identifying pixels matching target_bgr in the first 3 channels
        color_mask = np.all(img[:, :, :3] == target_bgr, axis=-1)

        # Force alpha channel (index 3) to 0 (fully transparent) where the mask evaluates to True
        img[color_mask, 3] = 0
        return img

    def _expand_canvas(self, img: np.ndarray) -> np.ndarray:
        """Adds standard empty, fully transparent border around the image frame."""
        p = self.config.padding
        if p == 0:
            return img

        logger.info(f"Expanding canvas by adding {p}px of padding to all edges...")
        # Use copyMakeBorder with BORDER_CONSTANT and transparent color value (0, 0, 0, 0)
        padded_img = cv2.copyMakeBorder(
            img,
            top=p,
            bottom=p,
            left=p,
            right=p,
            borderType=cv2.BORDER_CONSTANT,
            value=(0, 0, 0, 0),
        )
        return padded_img


def main() -> None:
    """Main application entry point."""
    config = parse_arguments()
    processor = ImageProcessor(config)
    processor.process()


if __name__ == "__main__":
    main()
