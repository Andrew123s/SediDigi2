# sobel_live.cpp – live Sobel preview via identity handoff

## Overview

Live preview of the camera feed with real-time Sobel edge detection,
using the `identity` element's `handoff` signal for in-place processing.
No video file is written – display only.

## Pipeline

```
nvarguscamerasrc → nvvidconv (NVMM → sysmem) → identity name=proc
  ↓ [ handoff: cv::Sobel on Y plane ]
  → nvvidconv (sysmem → NVMM) → nvegltransform → nveglglessink
```

The source is scaled to `--width` (default 1280, 4:3) before the identity
element so the Sobel processing runs at preview resolution.

## Build

```bash
cmake -S . -B build
cmake --build build
```

## Usage

```bash
./build/sobel_live
       [--sensor-id <n>] [--framerate <num/den>]
       [--tnr-mode <0|1|2>] [--tnr-strength <f>]
       [--ee-mode <0|1|2>] [--exposuretime <ns>]
       [--width <n>]
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
| `--width` | `1280` | `> 0, % 4` | Preview width (height = 3/4 width) |

### Example

```bash
./build/sobel_live --width 1920 --exposuretime 47000000
```

Press ENTER or close the preview window to stop.
