# PCBVisor Script Helper — High-Level Requirements

**Application Name:** PCBVisor Script Helper  
**Platform:** Windows Desktop (C# / WinForms, .NET 8+)  
**Language:** English  
**Author:** G. OZKESER  
**Document Version:** 1.0  
**Last Updated:** 2026-07-13  

---

## 1. Purpose & Scope

PCBVisor Script Helper is a Windows desktop GUI application that wraps a four-stage Python script pipeline used to detect and display fiducial markers on PCB images. The application allows users to:

- Configure each script's parameters through a structured, validated UI (no command-line knowledge required).
- Execute the pipeline stage by stage or as a single automated run.
- Monitor live console output from each script in an integrated log panel.
- View the final annotated output image (`_final.png`) directly inside the application with zoom and pan support.
- Save and reload named **profiles** for reusable file-set and parameter configurations.

---

## 2. Pipeline Overview

The four Python scripts run in the following fixed sequence. Each stage's output feeds the next:

| Step | Script | Key Inputs | Key Output |
|------|--------|-----------|------------|
| 1 | `expand_image.py` | Input PNG image | Expanded PNG (`*_E.png`) |
| 2 | `fid_finder.py` | Expanded PNG | Annotated PNG + JSON candidates (`*_fiducial_candidates.json`) |
| 3 | `origin_finder.py` | Candidates JSON + Fiducials CSV | Origin JSON (`*_fiducial_candidates_origin.json`) — embeds transformation matrix, origin pixel, layer, and matched fiducials |
| 4 | `fid_display.py` | Original PNG + Origin JSON | Final marked PNG (`*_final_.png`) |

> **Note:** The UI must automatically propagate output paths between stages so the user does not need to manually wire them.

---

## 3. Application Layout (High-Level)

The main window is divided into four logical regions:

```
+------------------------------------------------------------------+
|  Menu Bar: File | Profiles | Help                                |
+------------------------------------------------------------------+
|  Toolbar: [Profile: v Dropdown]  [Save Profile]  [Load Profile]  |
|           [  Run All  ]                                          |
+-------------------------------+----------------------------------+
|                               |                                  |
|   LEFT PANEL                  |   RIGHT PANEL                    |
|   Script Configuration        |   Image Viewer                   |
|   (Tab-based, one tab         |   [ Input Image | Output Image ] |
|    per script stage)          |   (Integrated, zoom + pan)       |
|                               |                                  |
+-------------------------------+----------------------------------+
|  BOTTOM PANEL - Live Log Output                                  |
|  (Scrollable, real-time stdout display per running script)       |
+------------------------------------------------------------------+
```

### 3.1 Left Panel — Script Configuration Tabs

Four tabs, one per script, labeled:
1. **Step 1 – Expand Image**
2. **Step 2 – Fiducial Finder**
3. **Step 3 – Origin Finder**
4. **Step 4 – Fiducial Display**

Each tab contains:
- **File inputs** (text fields + Browse buttons) for that stage's required files.
- **Parameter controls** (numeric spinners, sliders, color pickers, checkboxes) for all CLI arguments.
- **Individual `Run` button** to execute only that stage.
- **Status indicator** (colored dot/icon): Idle / Running / Success / Error.

### 3.2 Right Panel — Integrated Image Viewer (2-Tab)

The image viewer contains two tabs that share identical zoom/pan controls:

#### Tab 1 — Input Image
- Automatically loads and displays the **Source PNG** as soon as the user selects it in the Common Inputs section (no need to run the pipeline first).
- Updates immediately whenever the Source PNG field changes to a valid file.
- Shows a placeholder message *"Select a Source PNG to preview the input image."* when no file is selected.

#### Tab 2 — Output Image
- Automatically loads and displays the **`_final.png`** produced by Step 4 after a successful run.
- Also updates if the user manually selects a different output file path in Step 4's parameter panel.
- Shows a placeholder message *"No output image yet — run the pipeline to generate results."* until Step 4 has completed successfully.
- After Step 4 completes, the viewer **automatically switches to this tab** to bring the result into focus.

#### Shared Controls (both tabs)
- **Mouse-wheel zoom** and **click-drag pan**.
- Zoom percentage indicator with **Fit to Window** and **1:1** toggle buttons.
- **Open in Explorer** button to reveal the current image file in Windows Explorer.
- **Save As…** button to copy the currently displayed image to a user-chosen location.

### 3.3 Bottom Panel — Live Log

- Scrollable, read-only rich text area.
- Displays stdout/stderr from the currently running script in real time.
- Color-coded lines: standard output (white/light), warnings (yellow), errors (red), success markers (green).
- **Clear** button and **Copy to Clipboard** button.
- Each stage run is preceded by a visible separator/header showing the script name and timestamp.

---

## 4. Functional Requirements

### 4.1 Global File Inputs (Shared Across Stages)

These files are referenced by multiple stages and should be set once in a **Common Inputs** section (e.g., above the tab strip or on a dedicated "Inputs" pane):

| Field | Description |
|-------|-------------|
| **Source PNG** | The original, unmodified PCB image (`.png`) — used by Step 1 and Step 4. Selecting this field immediately loads the image into the **Input Image** tab of the viewer. |
| **Fiducials CSV** | The real-world fiducial coordinate file (`.csv`) — used only by Step 3. |
| **Working Directory** | Directory where all intermediate and output files will be written. Defaults to the source PNG's directory. |
| **Python Executable** | Path to the Python interpreter (e.g., `python.exe`). Auto-detected from PATH; user-overridable. |
| **Scripts Directory** | Path to the folder containing the four `.py` files. Defaults to the application's own directory. |

### 4.2 Step 1 — Expand Image (`expand_image.py`)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| Input PNG | File path | *(from Global → Source PNG)* | Auto-populated from global input. |
| Output path | File path | `*_E.png` (auto-derived) | Editable; auto-derived if left blank. |
| Padding (px) | Integer spinner | 125 | Pixels added to all four edges. |
| Transparent color (R,G,B) | Three integer spinners or color picker | 254, 254, 254 | Color key converted to transparency. |

**Auto-propagation:** On success, the output path is automatically populated as the **Input PNG** for Step 2.

### 4.3 Step 2 — Fiducial Finder (`fid_finder.py`)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| Input PNG | File path | *(from Step 1 output)* | Auto-populated; manually editable. |
| Output directory | Directory path | *(Working Directory)* | Where annotated PNG and JSON are written. |
| Canny Threshold | Float spinner | 100.0 | Upper threshold for Canny edge detection. |
| Min Circularity | Float slider (0.0–1.0) | 0.75 | Minimum circularity score for circle acceptance. |
| Min Radius (px) | Integer spinner | 14 | Minimum circle radius in pixels. |
| Max Radius (px) | Integer spinner | 18 | Maximum circle radius in pixels. |
| Debug Mode | Checkbox | Off | Generates intermediate step images when enabled. |

**Auto-propagation:** On success, the JSON candidates file path is auto-populated as the **JSON input** for Step 3.

### 4.4 Step 3 — Origin Finder (`origin_finder.py`)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| JSON Candidates | File path | *(from Step 2 output)* | Auto-populated; manually editable. |
| Fiducials CSV | File path | *(from Global → Fiducials CSV)* | Auto-populated from global input. |
| Layer | Dropdown | Auto-detect | `BottomLayer` / `TopLayer` / Auto-detect from filename. |
| Output JSON path | File path | `*_origin.json` (auto-derived) | Editable; auto-derived if left blank. |
| Ratio Tolerance | Float spinner | 0.01 | Normalized distance tolerance for candidate filtering. |

**Auto-propagation:** On success, the output origin JSON path is auto-populated as the **JSON input** for Step 4.

### 4.5 Step 4 — Fiducial Display (`fid_display.py`)

> **Note:** This script no longer requires a Fiducials CSV. All matched fiducial coordinates, radii, designators, and the layer identifier are read directly from the Origin JSON produced by Step 3 (`matched_fiducials` and `layer` fields).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| Image PNG | File path | *(from Global → Source PNG)* | Auto-populated from global input. |
| Origin JSON | File path | *(from Step 3 output)* | Auto-populated; manually editable. Contains transformation matrix, origin pixel, layer, and matched fiducials. |
| Layer | Dropdown | Auto-detect | `BottomLayer` / `TopLayer` / Auto-detect from JSON `layer` field, then from filename, then defaults to `BottomLayer`. |
| Fiducial Radius Offset (px) | Integer spinner | 10 | Added to the detected fiducial radius to prevent markers from overlapping the physical pad image (`FIDUCIAL_RADIUS_OFFSET_PX`). |
| Output marked PNG | File path | `*_final.png` (auto-derived) | Editable; auto-derived from the image filename if left blank. |

**Boundary auto-expansion:** If the computed origin pixel lies slightly outside the image boundaries (within ±100 px), the script automatically pads the canvas with transparent pixels. No user action is required; this is noted in the log output.

**Post-run:** On success, the `_final.png` output is automatically loaded into the **Output Image** tab of the integrated viewer, and the viewer switches to that tab automatically.

### 4.6 Run All

- A prominent **Run All** button in the toolbar executes Steps 1 → 2 → 3 → 4 sequentially.
- The pipeline halts immediately if any step exits with a non-zero return code.
- While running, the button label changes to **Stop** and clicking it cancels the active script process.
- The currently executing step's tab is automatically brought to the foreground.

### 4.7 Profile Management

A **profile** is a named snapshot of all current settings (file paths, parameters for all four steps). Profiles are stored as JSON files in a user-configurable directory (default: `%APPDATA%\PCBVisorScriptHelper\Profiles\`).

| Action | Description |
|--------|-------------|
| **New Profile** | Reset all settings to defaults and clear the current profile name. |
| **Save Profile** | Save current settings under the active profile name. Prompt for name if unnamed. |
| **Save Profile As…** | Save as a new profile with a different name. |
| **Load Profile** | Open a file dialog or dropdown to select and load a saved profile. |
| **Delete Profile** | Remove the selected profile (with confirmation dialog). |
| **Recent Profiles** | File menu lists the last 5 opened profiles for quick access. |
| **Auto-save on exit** | Optionally save the current state as a `_last_session` profile on application close. |

### 4.8 Python Environment Detection

- On first launch, the application searches for `python.exe` in `PATH` and common virtual environment locations.
- If not found, a prominent inline warning is shown with a **Browse…** button to locate the interpreter.
- The detected path persists in application settings.

---

## 5. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| **Responsiveness** | Script execution must run on a background thread; the UI must remain fully responsive (no freezing). |
| **Error Handling** | Each script's non-zero exit code must produce a clear, user-readable error message in the log panel and a status icon change on the corresponding tab. |
| **Validation** | File path fields must validate that the referenced file exists before allowing a stage to run; numeric fields must enforce valid ranges. Invalid fields are highlighted in red with a tooltip explaining the constraint. |
| **Auto-path propagation** | Intermediate file paths derived from naming conventions (`*_E.png`, `*_fiducial_candidates.json`, etc.) must be computed automatically and kept in sync when the source PNG or working directory changes. |
| **Persistence** | All settings (Python path, scripts directory, window size/position, last used profile) are persisted in `%APPDATA%\PCBVisorScriptHelper\settings.json`. |
| **Zoom/Pan Performance** | The image viewer must handle images up to 8000 x 8000 px without lag, using efficient rendering (e.g., clipped drawing, LOD). |
| **Log Buffer** | The log panel must cap its buffer (e.g., 5,000 lines) to prevent memory growth during long runs, with automatic scroll-to-bottom behavior. |
| **Process Isolation** | Each Python script is launched as a child process (`System.Diagnostics.Process`). stdout and stderr are piped and displayed in real time. |
| **Cancellation** | Clicking **Stop** while a script is running sends a termination signal and updates the status indicator to "Cancelled". |
| **.NET Version** | Target .NET 8 LTS (or later). WinForms project. |

---

## 6. UX & Accessibility Guidelines

- **Step numbering** and visual breadcrumb (Step 1 → 2 → 3 → 4) give users a clear sense of progress.
- **Tooltips** on every parameter control explain what the parameter does and what values are acceptable, referencing the underlying Python argument name (e.g., `--canny-threshold`).
- **Keyboard shortcuts**: `F5` = Run All, `Ctrl+S` = Save Profile, `Ctrl+O` = Load Profile, `Ctrl+W` = Clear log.
- **Drag-and-drop**: PNG and CSV files can be dragged onto the corresponding file-path fields.
- File-path fields that contain a valid path show a small green check icon; invalid or empty required fields show a red warning icon.
- The image viewer shows a "No output image yet — run the pipeline to generate results." placeholder when empty.

---

## 7. Out of Scope (v1.0)

- Editing Python scripts from within the application.
- Batch processing of multiple PCB images in a single run.
- Reporting / export to PDF or Excel.
- Remote / networked execution of Python scripts.
- Support for macOS or Linux.
