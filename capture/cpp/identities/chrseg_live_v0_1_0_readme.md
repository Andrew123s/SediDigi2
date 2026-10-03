# chrseg_live v0.1.0 – chromatic segmentation live preview via identity handoff

## Overview

Live preview of the camera feed with real‑time chromatic segmentation in LAB colour space. 
The Y plane of the NV12 frame is replaced with a binary foreground mask (white = detected object, black = background),
so the preview window shows a grayscale mask image.

Uses the `identity` element's `handoff` signal. 
The median background colour is computed from the first frame only (histogram‑based O(n) per channel). 
CLAHE algorithm (Contrast Limited Adaptive Histogram Equalization) was discarded.

## Pipeline

```
nvarguscamerasrc → nvvidconv (NVMM → sysmem, 4032×3040)
  → identity name=proc
      ↓ [ handoff: NV12 → BGR → LAB → inRange → mask → replace Y ]
  → nvvidconv (sysmem → NVMM, scale to display size)
  → nvegltransform → nveglglessink
```

## Build

```bash
cmake -S . -B build
cmake --build build
```

## Usage

```bash
./build/chrseg_live_v0_1_0
       [--sensor-id <n>] [--framerate <num/den>]
       [--tnr-mode <0|1|2>] [--tnr-strength <f>]
       [--ee-mode <0|1|2>] [--exposuretime <ns>]
       [--width <n>] [--delta <n>]
```

### Flags

| Flag | Default | Valid | Description |
|---|---|---|---|
| `--sensor-id` | `0` | `>= 0` | Camera sensor ID |
| `--framerate` | `21/1` | `num/den` | Framerate override |
| `--tnr-mode` | `1` | `0,1,2` | Temporal Noise Reduction |
| `--tnr-strength` | `0.1` | `0.0–1.0` | Only when `--tnr-mode > 0` |
| `--ee-mode` | `0` | `0,1,2` | Edge Enhancement |
| `--exposuretime` | `2500000` | `> 0` | Exposure time in ns |
| `--width` | `1280` | `> 0, % 4` | Display width (height = 3/4 width) |
| `--delta` | `10` | `0–100` | Tolerance from median background (%) |

Higher `--delta` = less sensitive (more pixels classified as background).

### Example

```bash
./build/chrseg_live_v0_1_0 --delta 15 --exposuretime 47000000
```

Press ENTER or close the preview window to stop.

## Optimisation ideas

- **Work in YUV directly** – skip BGR→Lab conversion entirely by thresholding in the native NV12 colour space (Y = luma, U/V = chroma). Would cut the pipeline to `NV12 → inRange → mask`.
- **Downscale mask** – shrink the mask to ¼ before morphology, then upscale back.
- **GPU acceleration** – `cv::cuda` variants available on Jetson Orin Nano.
