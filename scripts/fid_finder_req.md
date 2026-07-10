# fid_finder Requirements Document

## 1. Project Overview

fid_finder is a command-line tool for detecting circular fiducial markers in PNG images. It uses single-pass contour analysis with circularity and radius filtering to find circles, deduplicates close detections, and exports annotated images and JSON metadata.

The tool is implemented in Python using OpenCV (cv2) and NumPy.

## 2. Algorithm Flow

### 2.1. General Working Principle

1. Read input PNG image
2. Preprocess: grayscale conversion → median blur → Canny edge detection
3. Contour analysis with circularity and radius filtering
4. Deduplicate close detections (spatial + radius tolerance)
5. Annotate the original image with detected circles
6. Export fiducial candidate properties to JSON metadata
7. Generate execution log

### 2.2. Step-by-Step Process Detail

| Step | Operation | Description |
|------|-----------|-------------|
| 1 | Image Reading | Load PNG via `cv2.imread()` |
| 2 | Grayscale Conversion | BGR → Grayscale via `cv2.cvtColor()` |
| 3 | Median Blur | 5x5 kernel noise reduction via `cv2.medianBlur()` |
| 4 | Canny Edge Detection | Low threshold = canny_threshold/2, High threshold = canny_threshold |
| 5 | Circle Detection | Contour analysis with circularity/radius constraints |
| 6 | Deduplication | Merge nearby detections (spatial tolerance: 3px, radius tolerance: 3px) |
| 7 | Annotation & Output | Draw circles/IDs on image, write JSON metadata, write log file |

## 3. Detection Parameters

Detection parameters are provided via optional CLI arguments. All parameters have sensible defaults.

| Parameter | CLI Flag | Default | Description |
|-----------|:--------:|:-------:|-------------|
| Canny threshold | `--canny-threshold` | 100.0 | Upper threshold for Canny edge detection (low = half of this value) |
| Min circularity | `--min-circularity` | 0.75 | Minimum circularity for circle detection (4πA/P², 1.0 = perfect circle) |
| Min radius | `--min-radius` | 14 | Minimum radius in pixels for detected circles |
| Max radius | `--max-radius` | 18 | Maximum radius in pixels for detected circles |

### 3.1. Typical Values

- Canny threshold: 80–150
- Circularity: 0.70–0.90
- Min radius: 10–16 (for small fiducials)
- Max radius: 16–24 (for small fiducials)

## 4. Debug and Log System

### 4.1. `--debug` Flag

The `--debug` flag is a boolean option. When provided, the tool generates all intermediate debug output files. When omitted, only the final outputs (annotated image, JSON metadata, log file) are produced.

### 4.2. Debug Mode Outputs

When `--debug` is active, the following intermediate files are generated:

| Debug File | Content | Corresponding Step |
|------------|---------|-------------------|
| `{input}_step2_out.png` | Grayscale converted image | Step 2 |
| `{input}_step3_out.png` | Median-blurred image | Step 3 |
| `{input}_step4_out.png` | Canny edge detection result | Step 4 |
| `{input}_step5_out.png` | Detection visualization (green outlines, red centers) | Step 5 |

### 4.3. Step-Based File Naming Convention

All debug files follow the naming pattern:

```
{input_filename_stem}_step{number}_out.png
```

Where `{number}` corresponds to the algorithm step (2-5) that produced the file.

## 5. Command Line Interface (CLI)

### 5.1. Argument List

| Argument | Type | Required | Default | Description |
|----------|------|:--------:|:-------:|-------------|
| `-i, --input` | str | Yes | — | Path to input PNG image |
| `-o, --output-dir` | str | No | Input file's directory | Output directory for all generated files |
| `--canny-threshold` | float | No | 100.0 | Upper threshold for Canny edge detection |
| `--min-circularity` | float | No | 0.75 | Minimum circularity for circle detection |
| `--min-radius` | int | No | 14 | Minimum radius in pixels |
| `--max-radius` | int | No | 18 | Maximum radius in pixels |
| `--debug` | flag | No | Not set | Enable debug mode (generates all intermediate outputs) |

### 5.2. Usage Examples

```bash
# Basic usage with defaults
python fid_finder.py -i input.png

# Custom detection parameters
python fid_finder.py -i input.png --canny-threshold 125 --min-circularity 0.80 --min-radius 15 --max-radius 17

# Custom output directory
python fid_finder.py -i input.png -o ./results

# Debug mode for analysis
python fid_finder.py -i input.png --debug

# Full options
python fid_finder.py -i input.png --canny-threshold 125 --min-circularity 0.80 --min-radius 15 --max-radius 17 -o ./results --debug
```

## 6. Output Files

### 6.1. Annotated Image

- **Filename:** `{input_stem}_annotated.png`
- **Location:** Output directory
- **Content:** Original image with green circle boundaries, red center points, and blue ID labels.

### 6.2. JSON Metadata

- **Filename:** `{input_stem}_fiducials.json`
- **Location:** Output directory
- **Content:** Array of fiducial candidate objects with the following structure:

```json
[
    {
        "fid_candidate_id": 1,
        "center_x": 127.26,
        "center_y": 1628.493,
        "radius_px": 15.657
    }
]
```

| Field | Type | Description |
|:-----:|:----:|:-----------:|
| `fid_candidate_id` | integer | Sequential ID assigned to each detected candidate (1-based) |
| `center_x` | float | X-coordinate of the circle center in pixels |
| `center_y` | float | Y-coordinate of the circle center in pixels |
| `radius_px` | float | Radius of the detected circle in pixels |

### 6.3. Debug Intermediate Files

Generated only when `--debug` is specified. See Section 4.2 for details.

### 6.4. Log File

- **Filename:** `{input_stem}_log.txt`
- **Location:** Output directory
- **Content:** Full execution log including parameters, detected circles, progress messages, and any warnings or errors. Output is mirrored to both stdout and the log file.

## 7. Error Handling

| Error Scenario | Behavior |
|----------------|----------|
| Input file not found | Exit with `FileNotFoundError` and message |
| Invalid image file | Exit with `ValueError` and message |
| Cannot write output file | Exit with `OSError` and message |
| PNG format check fails | Exit with error message (stderr) |

## 8. Future Development Notes

- Support for additional image formats beyond PNG
- Parallel processing for batch image analysis
- Configurable blur kernel size
- Region of interest (ROI) filtering
- Adaptive Canny thresholding
- GUI for parameter tuning and visualization