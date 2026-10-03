# chrseg_live v0.1.3 – full-resolution GPU chromatic segmentation

## Overview

GPU-accelerated chromatic segmentation using CUDA 12.6 + NVIDIA NPP on Jetson Orin Nano.

**Key difference from v0.1.2:** GPU always processes at the camera's full native resolution
(4032×3040). The `--width` flag only controls the display size — the second `nvvidconv`
downscales the already-masked frame for the preview window.

This gives the highest possible segmentation quality because the per-pixel B/G/R
threshold operates on the original sensor data without prior downscaling.

- Colour conversion (NV12 → BGR) via NPP
- Foreground mask via per-channel inRange(B/G/R) + cross-channel AND
- Mask applied to Y plane via AND → background L=0, foreground L preserved, UV=128

**No OpenCV dependency.** Median histogram computed in plain C on first frame.

## Pipeline

```
 nvarguscamerasrc (4032×3040 NVMM)
   → nvvidconv bl-output=false
   → video/x-raw,format=NV12,width=4032,height=3040 (sysmem)
   → identity name=proc
       ↓ [ handoff: NV12 upload (18 MB) → GPU (NV12→BGR→per-channel inRange→AND→NOT→mask)
         → mask AND Y → download modified Y + UV=128 ]
   → nvvidconv (scale to display size)
   → video/x-raw(memory:NVMM),width=<display_w>,height=<display_h>
   → nvegltransform → nveglglessink
```

### GPU processing flow (per frame, 4032×3040)

| Step | API | Time (est.) |
|------|-----|-------------|
| Upload Y + UV (18 MB) | `cudaMemcpy2D` | ~15 ms |
| NV12 → BGR | `nppiNV12ToBGR_8u_P2C3R` | ~5 ms |
| BGR → 3 planes | `nppiCopy_8u_C3P3R` | ~3 ms |
| Per-channel inRange (B, G, R) | `nppiCompareC_8u_C1R` (×6) + `nppiAnd_8u_C1R` (×3) | ~5 ms |
| Combine channels + invert | `nppiAnd_8u_C1R` (×2) + `nppiNot_8u_C1R` | ~2 ms |
| Mask AND Y + download | `nppiAnd_8u_C1R` + `cudaMemcpy2D` | ~12 ms |
| **Total GPU** | | **~42 ms** (~24 fps) |

The camera delivers 21 fps, so GPU processing at full resolution is **not** the bottleneck.

## Memory

| Buffer | Size | Location |
|--------|------|----------|
| Y | 4032×3040 = 12 MB | host + GPU |
| UV | 4032×1520 = 6 MB | host + GPU |
| BGR | 4032×3040×3 = 37 MB | GPU only |
| Plane B | 4032×3040 = 12 MB | GPU only (reused as B-mask) |
| Plane G | 4032×3040 = 12 MB | GPU only (reused as G-mask) |
| Plane R | 4032×3040 = 12 MB | GPU only (reused as R-mask) |
| Tmp | 4032×3040 = 12 MB | GPU only |
| Mask | 4032×3040 = 12 MB | GPU only |
| **Total GPU** | **~117 MB** | |

All GPU buffers allocated once on first frame.

## Build

```bash
cmake -S identities -B identities/build
cmake --build identities/build
```

**Prerequisites:** CUDA 12.6, NPP libraries (JetPack / CUDA Toolkit).

## Usage

```bash
./identities/build/chrseg_live_v0_1_3
       [--sensor-id <n>] [--framerate <num/den>]
       [--tnr-mode <0|1|2>] [--tnr-strength <f>]
       [--ee-mode <0|1|2>] [--exposuretime <ns>]
       [--width <n>] [--delta <n>] [--benchmark] [--debug]
```

### Flags

| Flag | Default | Valid | Description |
|------|---------|-------|-------------|
| `--sensor-id` | `0` | `>= 0` | Camera sensor ID |
| `--framerate` | `21/1` | `num/den` | Framerate in Caps (immer gesetzt) |
| `--tnr-mode` | `1` | `0,1,2` | Temporal Noise Reduction |
| `--tnr-strength` | `0.1` | `0.0–1.0` | Only when `--tnr-mode > 0` |
| `--ee-mode` | `0` | `0,1,2` | Edge Enhancement |
| `--exposuretime` | `2500000` | `> 0` | Exposure time in ns |
| `--width` | `1280` | `> 0, % 4` | **Display only** display width (height = 3/4), based on 4032×3040 resolution |
| `--delta` | `10` | `0–100` | Tolerance from median background (%) |
| `--benchmark` | off | flag | Print rolling avg/min/max frame time every 30 frames |
| `--debug` | off | flag | Verbose GPU error messages |

### Example

```bash
./identities/build/chrseg_live_v0_1_3 --delta 15 --exposuretime 47000000 --benchmark
```

Press ENTER or close the preview window to stop.

## Differences from v0.1.2

- **Full-resolution GPU processing**: GPU always operates at 4032×3040 regardless of display size
- **`--width` only affects display**: the second `nvvidconv` downscales the processed frame
- **Median computed from full resolution**: better colour statistics (12M pixels instead of ~1.2M)
- **GPU buffer allocation**: always at full 4032×3040 (~117 MB)
- **Pipeline**: GPU resolution and display resolution are now independent in the pipeline string

## Known Issues

1. **Morphology crash** — `nppiErode_8u_C1R` raises `CUDA_KERNEL_EXECUTION_ERROR` at 4032×3040. Disabled.
2. **BGR vs LAB** — Thresholds directly in BGR (not Lab). Tune `--delta` accordingly.
3. **nvvidconv stride padding** — `GstVideoMeta` fallback to `stride = width` if absent.
4. **GPU memory** — ~117 MB permanently allocated. May conflict with other GPU applications.
