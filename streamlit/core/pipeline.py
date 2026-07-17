"""
PCBVisor — Pipeline Orchestrator

Runs all 22 steps in sequence, collecting StepResult objects.
Stops on first failure and records which step failed.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np

from processing.logger import PipelineLogger
from processing.results import StepResult
from processing import expand, detect, origin, display


@dataclass
class PipelineParams:
    """All tunable pipeline parameters in one flat structure."""
    # Group A: Expansion
    padding: int = 125
    transparent_r: int = 254
    transparent_g: int = 254
    transparent_b: int = 254
    transparent_tolerance: int = 3

    # Group B: Edge detection
    edge_method: str = "canny"          # "canny" | "binary"
    canny_threshold: float = 100.0
    binary_threshold: int = 127
    binary_invert: bool = False

    # Group B: Detection filters
    min_circularity: float = 0.75
    min_radius: int = 14
    max_radius: int = 18
    proximity_tolerance: int = 64

    # Group C: Origin
    layer: str = "auto"
    ratio_tolerance: float = 0.01

    # Group D: Display
    marker_shape: str = "reticle"
    line_thickness: int = 3
    fiducial_color_hex: str = "#00FF00"
    marker_size_multiplier: float = 3.0
    fiducial_radius_offset: int = 10
    show_labels: bool = True
    show_coordinates: bool = False
    origin_marker_size: int = 40
    origin_color_hex: str = "#FFFFFF"

    def hash(self) -> str:
        """MD5 hash of the parameter dict for change detection."""
        d = asdict(self)
        serialized = json.dumps(d, sort_keys=True)
        return hashlib.md5(serialized.encode()).hexdigest()


@dataclass
class PipelineState:
    """Complete state produced by one pipeline run."""
    steps: list[StepResult] = field(default_factory=list)
    success: bool = False
    total_duration_ms: float = 0.0
    failed_at: Optional[int] = None        # step_id of the first failure

    def step(self, step_id: int) -> Optional[StepResult]:
        for s in self.steps:
            if s.step_id == step_id:
                return s
        return None

    def last_image(self) -> Optional[np.ndarray]:
        """Return the image from the last successful step that has one."""
        for s in reversed(self.steps):
            if s.success and s.image is not None:
                return s.image
        return None

    def steps_with_images(self) -> list[StepResult]:
        return [s for s in self.steps if s.success and s.image is not None]


class PipelineRunner:
    """Executes all 22 steps. Stops on first failure."""

    def run(
        self,
        image_bytes: bytes,
        image_filename: str,
        csv_bytes: bytes,
        csv_filename: str,
        params: PipelineParams,
    ) -> PipelineState:
        t_total = time.perf_counter()
        state = PipelineState()

        # Use a temp directory for intermediate JSON files
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            stem = Path(image_filename).stem

            def add(result: StepResult) -> bool:
                state.steps.append(result)
                if not result.success:
                    state.failed_at = result.step_id
                return result.success

            # ── Group A: Image Expansion ──────────────────────────────────────

            log = PipelineLogger()
            r1 = expand.run_load_image(image_bytes, image_filename, log)
            if not add(r1):
                return self._finalize(state, t_total)
            img_raw = r1.image

            log = PipelineLogger()
            r2 = expand.run_convert_bgra(img_raw, log)
            if not add(r2):
                return self._finalize(state, t_total)
            img_bgra = r2.image

            log = PipelineLogger()
            r3 = expand.run_color_key(
                img_bgra,
                (params.transparent_r, params.transparent_g, params.transparent_b),
                params.transparent_tolerance,
                log,
            )
            if not add(r3):
                return self._finalize(state, t_total)
            img_keyed = r3.image

            log = PipelineLogger()
            r4 = expand.run_canvas_expand(img_keyed, params.padding, log)
            if not add(r4):
                return self._finalize(state, t_total)
            img_expanded = r4.image

            # ── Group B: Fiducial Detection ───────────────────────────────────

            log = PipelineLogger()
            r5 = detect.run_grayscale(img_expanded, log)
            if not add(r5):
                return self._finalize(state, t_total)

            log = PipelineLogger()
            r6 = detect.run_edge_detection(
                img_expanded,
                method=params.edge_method,
                canny_threshold=params.canny_threshold,
                binary_threshold=params.binary_threshold,
                binary_invert=params.binary_invert,
                logger=log,
            )
            if not add(r6):
                return self._finalize(state, t_total)

            # Re-compute edges numpy array needed for contour extraction
            _gray = (
                cv2.cvtColor(img_expanded, cv2.COLOR_BGRA2GRAY)
                if img_expanded.ndim == 3 and img_expanded.shape[2] == 4
                else cv2.cvtColor(img_expanded, cv2.COLOR_BGR2GRAY)
                if img_expanded.ndim == 3
                else img_expanded
            )
            if params.edge_method == "canny":
                edges_np = cv2.Canny(
                    _gray, params.canny_threshold / 2, params.canny_threshold
                )
            else:
                flag = cv2.THRESH_BINARY_INV if params.binary_invert else cv2.THRESH_BINARY
                _, edges_np = cv2.threshold(
                    _gray, params.binary_threshold, 255, flag
                )

            log = PipelineLogger()
            r7, contours = detect.run_contour_extraction(img_expanded, edges_np, log)
            if not add(r7):
                return self._finalize(state, t_total)

            log = PipelineLogger()
            r8, candidates = detect.run_circularity_filter(
                img_expanded, contours,
                params.min_circularity, params.min_radius, params.max_radius, log,
            )
            if not add(r8):
                return self._finalize(state, t_total)

            log = PipelineLogger()
            r9, candidates = detect.run_deduplication(img_expanded, candidates, log)
            if not add(r9):
                return self._finalize(state, t_total)

            log = PipelineLogger()
            r10, candidates = detect.run_min_enclosing_filter(img_expanded, candidates,
                                                               logger=log)
            if not add(r10):
                return self._finalize(state, t_total)

            log = PipelineLogger()
            r11, candidates = detect.run_inner_circle_pick(img_expanded, candidates, logger=log)
            if not add(r11):
                return self._finalize(state, t_total)

            log = PipelineLogger()
            r12, candidates = detect.run_proximity_filter(
                img_expanded, candidates, params.proximity_tolerance, logger=log
            )
            if not add(r12):
                return self._finalize(state, t_total)

            log = PipelineLogger()
            json_path = tmp / f"{stem}_fiducial_candidates.json"
            r13 = detect.run_annotate_and_export(img_expanded, candidates, stem, tmp, log)
            if not add(r13):
                return self._finalize(state, t_total)

            # ── Group C: Origin Computation ────────────────────────────────────

            log = PipelineLogger()
            r14, pixel_candidates = origin.run_load_candidates(json_path, img_expanded, log)
            if not add(r14):
                return self._finalize(state, t_total)

            log = PipelineLogger()
            r15, real_fiducials, resolved_layer = origin.run_load_real_fiducials(
                csv_bytes, csv_filename, image_filename, params.layer if params.layer != "auto" else None, log
            )
            if not add(r15):
                return self._finalize(state, t_total)

            log = PipelineLogger()
            r16, filtered_candidates = origin.run_candidate_filter(
                img_expanded, pixel_candidates, real_fiducials, params.ratio_tolerance, log
            )
            if not add(r16):
                return self._finalize(state, t_total)

            log = PipelineLogger()
            r17, px_matched, real_matched = origin.run_permutation_match(
                img_expanded, filtered_candidates, real_fiducials, log
            )
            if not add(r17):
                return self._finalize(state, t_total)

            log = PipelineLogger()
            r18, M_mat = origin.run_compute_transformation(px_matched, real_matched, log)
            if not add(r18):
                return self._finalize(state, t_total)

            log = PipelineLogger()
            origin_json = tmp / f"{stem}_origin.json"
            r19 = origin.run_origin_export(
                M_mat, px_matched, real_matched, resolved_layer, img_expanded, origin_json, log
            )
            if not add(r19):
                return self._finalize(state, t_total)

            # ── Group D: Final Display ─────────────────────────────────────────

            log = PipelineLogger()
            r20 = display.run_load_for_display(img_expanded, log)
            if not add(r20):
                return self._finalize(state, t_total)

            log = PipelineLogger()
            r21, img_with_origin, _ = display.run_draw_origin(
                r20.image,
                origin_json,
                origin_marker_size=params.origin_marker_size,
                origin_color_hex=params.origin_color_hex,
                line_thickness=params.line_thickness,
                logger=log,
            )
            if not add(r21):
                return self._finalize(state, t_total)

            log = PipelineLogger()
            r22 = display.run_draw_fiducials(
                r21.image,
                origin_json,
                marker_shape=params.marker_shape,
                fiducial_color_hex=params.fiducial_color_hex,
                line_thickness=params.line_thickness,
                marker_size_multiplier=params.marker_size_multiplier,
                fiducial_radius_offset=params.fiducial_radius_offset,
                show_labels=params.show_labels,
                show_coordinates=params.show_coordinates,
                logger=log,
            )
            add(r22)

        state.success = state.failed_at is None
        return self._finalize(state, t_total)

    def _finalize(self, state: PipelineState, t0: float) -> PipelineState:
        state.total_duration_ms = (time.perf_counter() - t0) * 1000
        state.success = state.failed_at is None
        return state
