"""
PCBVisor — Step Result Dataclasses
One dataclass per pipeline step. All extend StepResult base class.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class StepResult:
    """Base class for all pipeline step results."""

    step_id: int
    step_label: str
    success: bool
    duration_ms: float
    logs: list[str]
    # BGRA numpy array for display; None if the step produces no image
    image: np.ndarray | None
    # Key → value pairs shown in the statistics panel
    stats: dict[str, Any]
    error: str | None = None


# ─── Group A: Image Expansion ────────────────────────────────────────────────

@dataclass
class LoadImageResult(StepResult):
    width: int = 0
    height: int = 0
    channels: int = 0


@dataclass
class ConvertBGRAResult(StepResult):
    pass


@dataclass
class ColorKeyResult(StepResult):
    transparent_pixels: int = 0


@dataclass
class CanvasExpandResult(StepResult):
    new_width: int = 0
    new_height: int = 0
    padding_px: int = 0


# ─── Group B: Fiducial Detection ──────────────────────────────────────────────

@dataclass
class GrayscaleResult(StepResult):
    pass


@dataclass
class EdgeResult(StepResult):
    method: str = ""       # "canny" | "binary"
    threshold: float = 0.0


@dataclass
class ContourResult(StepResult):
    total_contours: int = 0


@dataclass
class CircularityFilterResult(StepResult):
    candidates_before: int = 0
    candidates_after: int = 0
    rejected: int = 0


@dataclass
class DeduplicateResult(StepResult):
    candidates_before: int = 0
    candidates_after: int = 0


@dataclass
class MinEnclosingFilterResult(StepResult):
    candidates_before: int = 0
    candidates_after: int = 0


@dataclass
class InnerCirclePickResult(StepResult):
    candidates_before: int = 0
    candidates_after: int = 0


@dataclass
class ProximityFilterResult(StepResult):
    candidates_before: int = 0
    candidates_after: int = 0


@dataclass
class AnnotateResult(StepResult):
    detected_count: int = 0
    json_path: Path | None = None


# ─── Group C: Origin Computation ─────────────────────────────────────────────

@dataclass
class LoadCandidatesResult(StepResult):
    candidate_count: int = 0


@dataclass
class LoadRealFiducialsResult(StepResult):
    fiducial_count: int = 0
    layer: str = ""


@dataclass
class CandidateFilterResult(StepResult):
    algorithm: str = ""     # "exact_match" | "scale_pair_search" | "distance_ratio"
    m_before: int = 0
    n_target: int = 0
    scale_px_per_mm: float = 0.0


@dataclass
class PermutationMatchResult(StepResult):
    best_permutation: list[int] = field(default_factory=list)
    matched_pairs: int = 0


@dataclass
class ComputeTransformResult(StepResult):
    transform_type: str = ""
    rmse_px: float = 0.0
    scale_px_per_mm: float = 0.0


@dataclass
class OriginExportResult(StepResult):
    origin_x: float = 0.0
    origin_y: float = 0.0
    output_path: Path | None = None
    json_bytes: bytes = b""


# ─── Group D: Final Display ───────────────────────────────────────────────────

@dataclass
class LoadForDisplayResult(StepResult):
    width: int = 0
    height: int = 0


@dataclass
class DrawOriginResult(StepResult):
    origin_in_bounds: bool = False
    origin_x: int = 0
    origin_y: int = 0


@dataclass
class DrawFiducialsResult(StepResult):
    fiducials_drawn: int = 0
