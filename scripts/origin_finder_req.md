# Origin Finder — Requirements Document

## 1. Overview

The **Origin Finder** computes the pixel location of the world origin `(0, 0)` by matching fiducial candidate pixel coordinates (from a JSON file) with their real-world millimeter coordinates (from a CSV file) using geometric transformation.

### 1.1 Inputs

| Input | Description | Source |
|-------|-------------|--------|
| JSON file | Detected fiducial candidates with pixel coordinates (`center_x`, `center_y`) and radius | Fiducial detection output |
| CSV file | Real fiducial designators with world coordinates (`Center-X(mm)`, `Center-Y(mm)`) and layer info | CAD / design export |
| Layer (optional) | Which PCB layer to process (`BottomLayer` or `TopLayer`) | Auto-detected from filename or explicitly provided via `--layer` |

### 1.2 Output

A JSON file containing:
- Transformation matrix (world mm → pixel)
- Origin pixel coordinates

All algorithmic details (matches, RMSE, permutation, etc.) are printed to console/log during execution but are not included in the output JSON.

---

## 2. CSV Parsing Rules

The CSV file may have non-standard formatting. The parser must handle all of the following:

### 2.1 BOM Handling
- The file is opened with `utf-8-sig` encoding to strip any Byte Order Mark (BOM) automatically.

### 2.2 Non-CSV Header Lines
- Lines preceding the actual CSV header row must be tolerated.
- **Example**: The first line may contain arbitrary text such as `{some text}`. Such lines are skipped if they do not contain the expected column headers.

### 2.3 Header Row Detection
- The parser scans lines sequentially to find the **first row** that contains **all four** required column names (regardless of column order):
  - `Designator`
  - `Layer`
  - `Center-X(mm)`
  - `Center-Y(mm)`
- The detection is **case-insensitive** for column name matching.
- Extra/unexpected columns in the header row are ignored (matched by name, not position).

### 2.4 Quoted Fields
- CSV fields may be quoted (e.g., `"FD4"`, `"BottomLayer"`). Quotes are stripped during parsing.

### 2.5 Unit Suffix in Coordinates
- Coordinate values may include a `"mm"` suffix (e.g., `"46.2216mm"`). The parser strips `"mm"` before converting to float.

### 2.6 Data Row Filtering
- Only rows where:
  - **Layer** matches the target layer (`BottomLayer` or `TopLayer`)
  - **Designator** starts with `FD` (case-insensitive)
- Rows with insufficient columns or unparseable coordinates are skipped with a warning.

### 2.7 Error Handling
- If no valid header row is found → raise `ValueError` listing expected columns.
- If no matching fiducial rows are found after filtering → raise `ValueError`.
- If the CSV file does not exist → raise `FileNotFoundError`.

---

## 3. Pixel Candidate Loading (JSON)

- The JSON file is a list of detected fiducial candidate objects.
- Each object must contain at minimum:
  - `fid_candidate_id` (integer)
  - `center_x` (float)
  - `center_y` (float)
- Each object may also include:
  - `radius_px` (float) — radius of the detected circle in pixels
- Example entry:
  ```json
  {
      "fid_candidate_id": 1,
      "center_x": 127.26,
      "center_y": 1628.493,
      "radius_px": 15.657
  }
  ```

---

## 4. Matching Pixel Candidates to Real Fiducials

This is the **most critical algorithm** in the script. It matches fiducial candidates (from image detection) to real fiducials (from CSV) between the two coordinate systems without relying on ordering, labels, or IDs.

### 4.1 Precondition

Let **M** = number of pixel candidates (from JSON), **N** = number of real fiducials (from CSV).

- If **M < N**: The script exits with an error (insufficient candidates).
- If **M == N**: Direct permutation matching is used (Section 4.2).
- If **M > N**: Distance ratio filtering (Section 4.5) is applied first to select the N best-matching candidates, then permutation matching is performed.

### 4.2 Algorithm Steps (Permutation Matching)

1. **Compute pairwise distance matrices** for both the pixel point set and the real point set:
   - `D_pixel[i][j]` = Euclidean distance between pixel point `i` and pixel point `j`
   - `D_real[i][j]` = Euclidean distance between real point `i` and real point `j`
   - Both are symmetric `N×N` matrices.

2. **Normalize each matrix** by its median non-zero distance:
   - `D_pixel_norm = D_pixel / median(D_pixel[D_pixel > 0])`
   - `D_real_norm = D_real / median(D_real[D_real > 0])`
   - This makes the matrices scale-independent (compensating for pixel↔mm unit difference).

3. **Brute-force permutation search** over all `N!` possible correspondences:
   - For each permutation `perm` of `[0, 1, ..., N-1]`:
     - Reorder the real distance matrix: `D_real_perm = D_real_norm[perm][:, perm]`
     - Score = sum of absolute differences between `D_pixel_norm` and `D_real_perm`
   - The permutation with the **lowest score** is selected as the best match.

4. **Re-order the real fiducial list** according to the best permutation, so the `i`-th real fiducial corresponds to the `i`-th pixel candidate.

### 4.3 Requirements

- Minimum **2 points** required; fewer raises `ValueError`.
- All points must not be coincident (distance matrices must have non-zero median), otherwise `ValueError`.
- The algorithm is deterministic (exhaustive over all permutations).

### 4.4 Limitations / Future Improvements

- For `N > 8`, `N!` becomes computationally prohibitive (>40k permutations). A future optimization could use Hungarian algorithm or point-set registration (e.g., ICP).

---

## 4.5 Distance Ratio Filtering for Large Candidate Sets (M > N)

When the number of pixel candidates from image processing (M) significantly exceeds the number of real fiducials from CSV (N), the brute-force permutation approach cannot be used directly since it requires M = N.

The following algorithm filters N best-matching candidates out of M candidates.

### 4.5.1 Overview

The algorithm uses the fact that the **ratios** of the N real points' pairwise distances are invariant under similarity/affine transformations. These ratios can be used to identify which M candidates form a congruent N-gon with the real points.

### 4.5.2 CLI Parameter

The tolerance for ratio matching is configurable via `--ratio-tolerance` (default: 0.01). Lower values mean stricter matching but fewer candidates.

### 4.5.3 Algorithm Steps

1. **Compute real normalized distance ratios**: Calculate the 3 pairwise distances between the real fiducials, normalize by their median, and sort:
   ```
   real_dists = [d(FD4,FD5), d(FD4,FD6), d(FD5,FD6)]
   real_norm = sorted(real_dists / median(real_dists))
   ```
   Log the real fiducial pair distances.

2. **Select the base real link**: Identify the pair of real fiducials with the maximum distance between them. Let this baseline link have indices $i_{max}, j_{max}$ and distance $d_{max}$ (in mm).
   - This baseline link is used to anchor the similarity transform.

3. **Bounding box scale estimation**: Compute the bounding box diagonal of all pixel candidates ($D_{px}$) and real mm coordinates ($D_{real}$). Estimate the expected scale:
   ```
   scale_est = D_px / D_real
   ```
   Allow a scale range of `[0.85 * scale_est, 1.15 * scale_est]` to filter out pixel pairs with unrealistic scale ratios, reducing computation and avoiding scale-coincident false matches.

4. **Similarity-constrained pair search**: Loop over all candidate pixel pairs $(a, b)$ with $a \neq b$:
   - Calculate pixel distance $D_{ab} = \text{dist}(a, b)$ and candidate scale $S = D_{ab} / d_{max}$.
   - If $S$ is outside the allowed scale range, discard the pair immediately.
   - Map $FD_{i_{max}} \to a$ and $FD_{j_{max}} \to b$. Evaluate **both** similarity transform models:
     * **Standard (reflection-free) Similarity**:
       ```
       s_x = (dx_real * dx_px + dy_real * dy_px) / d2_real
       s_y = (dx_real * dy_px - dy_real * dx_px) / d2_real
       t_x = pixel_pts[a, 0] - (s_x * real_p1[0] - s_y * real_p1[1])
       t_y = pixel_pts[a, 1] - (s_y * real_p1[0] + s_x * real_p1[1])
       ```
       And project: `x_px = s_x * x - s_y * y + t_x`, `y_px = s_y * x + s_x * y + t_y`.
     * **Reflecting (mirrored) Similarity** (for chirality-flipped layers):
       ```
       s_x = (dx_real * dx_px - dy_real * dy_px) / d2_real
       s_y = (dy_real * dx_px + dx_real * dy_px) / d2_real
       t_x = pixel_pts[a, 0] - (s_x * real_p1[0] + s_y * real_p1[1])
       t_y = pixel_pts[a, 1] - (s_y * real_p1[0] - s_x * real_p1[1])
       ```
       And project: `x_px = s_x * x + s_y * y + t_x`, `y_px = s_y * x - s_x * y + t_y`.
   - For each projected point, find the nearest candidate in pixel space.
   - Ensure the uniqueness constraint: no candidate is assigned to more than one real fiducial.
   - Verify individual distance error is under `max(15.0, 3.0 * scale * tolerance)` pixels.
   - If a valid mapping is found for all $N$ points, compute the RMSE.
   - Retain the subset of $N$ points with the lowest RMSE.

5. **Collinearity check**: Verify that the N selected points span 2D space. For N ≥ 3, compute the SVD of the centred N×2 coordinate matrix and inspect the second singular value. If it is less than 1.0 pixel, the points are nearly collinear and a warning is printed.

### 4.5.4 Performance (Similarity pre-filter)

| Step | Complexity | Notes |
|:-----|:----------:|:------|
| Base real link selection | O(N²) | Done once |
| Candidate pair scale filter | O(M²) | Filter out unrealistic scales |
| Similarity transform solving | O(M²_valid) | Fast analytical solution |
| Nearest neighbor lookup | O(M²_valid · N · M) | Vectorised distance checking |
| **Total Complexity** | **O(M² · N)** | **Very fast (less than 50ms for M=1000)** |

### 4.5.5 Tolerance Parameters

- **`--ratio-tolerance`** (default: `0.01`): Used to define the maximum allowed pixel mapping error via `max(15.0, 3.0 * scale * tolerance)`.
- **Bounding box scale bounds**: Automatically limits candidate pairs to those matching `[0.85 * scale_est, 1.15 * scale_est]`.

### 4.5.6 Generalization to N ≥ 2

The similarity-constrained pair search naturally generalizes to any $N \ge 2$. 
- For $N = 2$, any pair that falls within the scale constraints matches, and we pick the one with the lowest error.
- For $N \ge 3$, the baseline link is established by the two furthest real points, and the remaining $N-2$ points are validated geometrically.

---

## 5. Geometric Transformation

### 5.1 Transformation Type

| Number of points | Transformation Type | OpenCV Function |
|:----------------:|:------------------:|:---------------:|
| 2 | **Similarity** (scale + rotation + translation, 4 DOF) | `estimateAffinePartial2D` |
| 3+ | **Affine** (scale + rotation + shear + translation, 6 DOF) | `estimateAffine2D` |

Both use **RANSAC** with a reprojection threshold of 3.0 pixels for robustness against outliers.

### 5.2 Origin Computation

The world origin `(0, 0)` in pixel coordinates is simply the **translation component** of the affine matrix:

```
origin_x = M[0][2]
origin_y = M[1][2]
```

This is because applying the transformation to `(0, 0)`:
```
x_px = M[0][0] * 0 + M[0][1] * 0 + M[0][2] = M[0][2]
y_px = M[1][0] * 0 + M[1][1] * 0 + M[1][2] = M[1][2]
```

### 5.3 RMSE Calculation

- Project each real point into pixel space using the transformation.
- Compute the Euclidean distance between projected and actual pixel coordinates.
- RMSE = `sqrt(mean(squared_errors))` in pixels.

### 5.4 Error Handling

- If `estimateAffinePartial2D` or `estimateAffine2D` returns `None` (e.g., collinear points or RANSAC failure), raise `ValueError`.
- At least 2 points required; fewer raises `ValueError`.

---

## 6. Layer Detection

### 6.1 Auto-Detection from JSON Filename

If `--layer` is not provided, the layer is inferred from the JSON filename stem (case-insensitive substring matching):

| Substring in filename | Layer |
|:---------------------:|:-----:|
| `BOTTOM` or `BOT` | `BottomLayer` |
| `TOP` | `TopLayer` |

Longer substrings are checked first (e.g., `BOTTOM` before `BOT`) to avoid premature partial matches on filenames such as `…_BOTTOM_…`. If no substring matches, the script exits with an error asking the user to specify `--layer` explicitly.

### 6.2 CLI Layer Argument

The `--layer` argument accepts:
- `BottomLayer` / `TopLayer` (full names)
- `BOT` / `TOP` (shorthand, automatically expanded to full names)

---

## 7. Output JSON Structure

The output JSON contains only the essential data needed for downstream coordinate transformation. All algorithmic details (matches, RMSE, permutation, etc.) are printed to console/log during execution.

```json
{
    "transformation_matrix": [
        [M00, M01, M02],
        [M10, M11, M12]
    ],
    "origin_pixel": {"x": 123, "y": 789}
}
```

| Field | Type | Description |
|:-----:|:----:|:-----------:|
| `transformation_matrix` | 2×3 array of float | Affine/similarity matrix mapping world mm → pixel coordinates |
| `origin_pixel` | object with int `x`, `y` | Pixel coordinates of world origin `(0, 0)`, rounded to nearest integer |

The `origin_pixel` values are integers (rounded from the translation component of the transformation matrix) since sub-pixel precision is not required for origin location.

### 7.1 Console / Log Output

The output is structured into clearly labelled pipeline steps so that execution progress can be followed unambiguously. Each step is delimited by a `[*]` marker at the top level, with indented sub-items beneath it. The following information is printed (not included in the output JSON):

**Step 1 — Load pixel candidates**
- Input JSON path and number of candidates loaded.

**Step 2 — Load real fiducials**
- Input CSV path, layer, number of real fiducials, and their coordinates.

**Step 3 — Candidate count / similarity pre-filter** *(only when M > N)*
- `M` vs `N` summary and filter decision (exact match / running filter).
- Real fiducial geometry: pair distances.
- **[1/1] Similarity-constrained pair search**:
  - Baseline real link description.
  - Count of evaluated pairs (total vs valid scale).
  - Selected candidates with scale and similarity match RMSE.

**Step 4 — Permutation matching**
- Number of M! permutations evaluated.
- Best permutation indices.
- Matched-pairs table: `fid_candidate_id`, pixel coordinates, designator, real mm coordinates.

**Step 5–6 — Transformation**
- Transformation type (similarity / affine) and number of points.
- RMSE in pixels.

**Step 7 — Origin**
- World origin (0, 0) → pixel coordinates.

**Step 8 — Output**
- Path to the written JSON file.

---

## 8. CLI Arguments

| Flag | Long | Required | Default | Description |
|:----:|:----:|:--------:|:-------:|:-----------:|
| `-j` | `--json` | Yes | — | Path to the fiducial candidates JSON file |
| `-c` | `--csv` | Yes | — | Path to the real fiducials CSV file |
| `-l` | `--layer` | No | Auto-detect | Layer: `BottomLayer`, `TopLayer`, `BOT`, or `TOP` |
| `-o` | `--output` | No | `<json_stem>_origin.json` | Custom output JSON path |
| | `--ratio-tolerance` | No | 0.01 | Normalized distance tolerance for candidate filtering |

---

## 9. Error Handling & Exit Codes

| Condition | Exit Code | Message |
|-----------|:---------:|---------|
| JSON file not found | 1 | `File not found: <path>` |
| CSV file not found | 1 | `File not found: <path>` |
| CSV header row not found | 1 | `Could not find header row in CSV file...` |
| No FD fiducials for target layer | 1 | `No fiducial markers (designator starting with 'FD') found...` |
| Too few pixel candidates (M < N) | 1 | `Too few pixel candidates (M) for real fiducials (N).` |
| Fewer than 2 points | 1 | `At least 2 matching fiducial points are required.` |
| Cannot normalize (all coincident) | 1 | `Cannot normalize distance matrices: all points are coincident` |
| Transformation computation failed | 1 | `Transformation could not be computed...` |
| Layer auto-detection failed | 1 | `Could not auto-detect layer from filename...` |
| Distance ratio filtering failed | 1 | `Could not find a set of N pixel candidates matching...` |

---

## 10. Dependencies

- Python ≥ 3.8
- OpenCV (`cv2`)
- NumPy (`numpy`)
- Standard library: `argparse`, `csv`, `itertools`, `json`, `math`, `re`, `sys`, `pathlib`, `typing`

---

## 11. Usage Examples

### Basic usage (layer auto-detected from filename containing `BOT`):
```
python origin_finder.py -j results/00000000_D01_BOT_fiducials.json -c 00000000_D01_Fiducials.csv
```

### Explicit layer specification:
```
python origin_finder.py -j results/00000000_D01_BOT_fiducials.json -c 00000000_D01_Fiducials.csv --layer BottomLayer
```

### Custom output path:
```
python origin_finder.py -j results/00000000_D01_BOT_fiducials.json -c 00000000_D01_Fiducials.csv -o custom_output.json
```

### Custom ratio tolerance (for noisy images):
```
python origin_finder.py -j results/00000000_D01_BOT_fiducials.json -c 00000000_D01_Fiducials.csv --ratio-tolerance 0.02
```

### Visualization of origin and fiducials on image:
```
python fid_display.py -i 00000000_D01_BOT.png -c 00000000_D01_Fiducials.csv -j 00000000_D01_BOT_fiducial_candidates_origin.json
```