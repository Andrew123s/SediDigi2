# SediDigi/segmentation

Chromatic segmentation for extracting moving objects from videos with a static background. 
Uses LAB color-space background subtraction combined with SORT (Simple Online and Realtime Tracking) for multi-object tracking.

## Files

- **chromatic_segmentation_07072026.py** - Original script from Clément Schneider: background segmentation via LAB color space + SORT tracking
- **bg_segmentation_v0_1.py** - Variant with selectable background models (`-b median|frame|temporal`)
- **sort/__init__.py** - Wrapper package for SORT import (`from sort.sort import *`)
- **sort/sort.py** - Re-export from `sort_tracker` (pip package)

## Software Setup

### Create virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Install dependencies

```bash
pip install numpy scipy filterpy sort-tracker-py av opencv-python-headless tqdm
```

### SORT tracking (wrapper)

The script expects `from sort.sort import *`. The pip package `sort-tracker-py`
provides the `Sort` class under `sort_tracker`. A local wrapper package `sort/`
forwards the import.

## Usage

```bash
python chromatic_segmentation_07072026.py -i <video filename>
```

### Example with selectable background model

```bash
# Using temporal background model (per-pixel median over frames 0-14),
# delta 10 %, minimum object area 1500 px, with annotated video output (-D)
python bg_segmentation_v0_1.py -i BTK2_12__Ori_23_N__Funsoil__bg1__01.mov -b temporal --bg_frames 15 -d 10 -a 1500 -D
```

### Common use cases

```bash
# Quick start: default median background model, no tuning required
python bg_segmentation_v0_1.py -i <video filename>

# Quick start + annotated video output
python bg_segmentation_v0_1.py -i <video filename> -D

# First-frame background model (requires object-free first frame)
python bg_segmentation_v0_1.py -i <video filename> -b frame

# Temporal background model, smaller objects
python bg_segmentation_v0_1.py -i <video filename> -b temporal --bg_frames 10 -a 1500

# Halve effective fps to speed up processing / ease tracking of fast objects
python bg_segmentation_v0_1.py -i <video filename> -b temporal -l

# Original script with default parameters
python chromatic_segmentation_07072026.py -i <video filename>
```

### Options

| Parameter | Description | Default |
|---|---|---|
| `-i, --input` | Video file path | required |
| `-a, --min_area` | Minimum object area (px) | 5000 |
| `-H, --max_h` | Maximum object height (px) | 1000 |
| `-r, --resize` | Scale factor | 0.25 |
| `-n, --num_samples` | Images per object | 10 |
| `-d, --delta` | Deviation from background (%), per-channel LAB tolerance | 10 |
| `-b, --bg_model` | Background model: `median`, `frame`, `temporal` | median |
| `--bg_frames` | Frames collected for the `temporal` background model | 15 |
| `-D, --drawing` | Generate annotated video | off |
| `-c, --clahe` | Apply CLAHE | off |

## Troubleshooting

### NumPy / SciPy incompatibility

The system-installed `scipy` may be compiled against NumPy 1.x while a newer
NumPy 2.x is present. This causes `ImportError: numpy.core.multiarray failed to import`.
The virtual environment installs compatible versions automatically.

### SORT import fails

Ensure the `sort/` wrapper directory exists next to the script. It re-exports
from `sort_tracker` installed via `pip install sort-tracker-py`.

## Notes

### CLAHE (Contrast Limited Adaptive Histogram Equalization)

CLAHE improves local contrast in images by equalizing the histogram in small
tile regions rather than globally. A clip limit prevents over-amplification of
noise. In this script (`-c` flag), CLAHE is applied to the L channel (lightness)
of the LAB color image before background subtraction, which can improve
segmentation under uneven lighting conditions.

See also: [OpenCV CLAHE documentation](https://docs.opencv.org/4.x/d6/dc6/tutorial_histogram_eq_introduction.html)

## Background models

`bg_segmentation_v0_1.py` supports three background models (`-b`), all operating
in LAB color space. A pixel is classified as background if it lies within the
tolerance `delta` (`-d`, percentage of the LAB channel range) in **all three
channels**; everything else is foreground.

- **`median`** (default): a single scalar background color, the channel-wise
  median of the first frame. Background pixels are within `median ± delta` per
  channel. Assumes a uniform, temporally stable background color; struggles with
  spatial gradients/structure and slow global colour drift. Fastest, needs only
  one frame.
- **`frame`**: the first frame itself is the per-pixel background reference.
  Foreground pixels are those whose LAB difference to the reference exceeds
  `delta` in any channel. Handles spatially structured backgrounds, but
  **requires an object-free first frame** and degrades under slow sensor/colour
  drift.
- **`temporal`**: per-pixel median over the first `--bg_frames` frames (default
  15). Most robust: suppresses transient objects and sensor noise during the
  warm-up frames. Keeps `--bg_frames` full-resolution frames in memory until the
  median is computed. The reference is fixed after that window (later drift is
  not followed).

## Roadmap

- [ ] Test with more example videos
- [x] Chromatic segmentation in LAB color space
- [x] SORT tracking (Simple Online and Realtime Tracking)
- [x] Hardware acceleration detection (CUDA/QSV/VAAPI)
- [ ] GPU acceleration

## References

- [SORT: Simple Online and Realtime Tracking](https://arxiv.org/abs/1602.00763)
- [sort-tracker-py (PyPI)](https://pypi.org/project/sort-tracker-py/)
- [abewley/sort (GitHub)](https://github.com/abewley/sort)
