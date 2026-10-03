# chrseg_live v0.2.0

Chromatic segmentation live preview, now with video-file input support.

## What's new in v0.2.0

- **`--input <video-file>`**: read from a video file instead of the camera
- **Native resolution processing**: GPU buffers are allocated to the file's actual resolution (no fixed 4032×3040)
- **`decodebin`** auto-selects demuxer + decoder (MJPEG-AVI, H.264 MKV/MP4, ...)
- Camera flags are ignored (with a warning) in file mode
- File end → EOS → program exits

## Source modes

| Mode | Trigger | Source pipeline |
|------|---------|-----------------|
| Camera | default | `nvarguscamerasrc ... ! nvvidconv ! video/x-raw,format=NV12 ! identity(name=proc)` |
| File | `--input <file>` | `filesrc ! decodebin ! nvvidconv bl-output=false ! video/x-raw,format=NV12 ! identity(name=proc)` |

Everything downstream of `identity` (GPU Lab segmentation, threshold, morphology, masking, tee display/record branches) is identical in both modes.

## Architecture

**GPU pipeline (per frame, resolution = source resolution):**

```
upload NV12
  → [NPP] NV12→BGR
  → [CUDA] BGR→Lab
  → [CPU] median a/b (first frame)
  → [CUDA] threshold_ab → not_mask
  → [CUDA] erode → dilate (opening)
  → [CUDA] apply_mask to Y
  → download modified Y (UV untouched)
```

## CLI flags

| Option | Default | Description |
|--------|---------|-------------|
| `--input <file>` | camera | Read from video file instead of camera |
| `--record [file]` | off | Enable recording (re-encode to MJPEG-AVI) |
| `--no-mask` | off | Skip Y channel masking (original image) |
| `--no-morph` | off | Disable morphological opening |
| `--sensor-id <n>` | 0 | Camera sensor ID (ignored in file mode) |
| `--framerate <n/d>` | 21/1 | Camera framerate (ignored in file mode) |
| `--tnr-mode <0\|1\|2>` | 1 | TNR (ignored in file mode) |
| `--tnr-strength <f>` | 0.1 | TNR strength (ignored in file mode) |
| `--ee-mode <0\|1\|2>` | 0 | Edge enhancement (ignored in file mode) |
| `--exposuretime <ns>` | 2500000 | Exposure (ignored in file mode) |
| `--width <n>` | 1280 | Display width (4:3) |
| `--delta <n>` | 10 | Threshold % (0–100) |
| `--benchmark` | off | 30-frame timing stats |
| `--debug` | off | GStreamer debug |

In file mode, explicitly-passed camera flags produce `WARNING: --xxx ignored in file mode` but execution continues.

## Build

```bash
cmake -S identities -B identities/build && cmake --build identities/build --target chrseg_live_v0_2_0
```

## Usage

```bash
# Camera (unchanged behaviour)
./build/chrseg_live_v0_2_0

# Play a recorded video (from chrseg_live --record)
./build/chrseg_live_v0_2_0 --input <video filename>

# File with masking disabled
./build/chrseg_live_v0_2_0 --input <video filename> --no-mask

# Re-encode file to a new recording
./build/chrseg_live_v0_2_0 --input <video filename> --record <record filename>

# Benchmark GPU processing from file
./build/chrseg_live_v0_2_0 --input <video filename> --benchmark
```

Press ENTER or close the window to stop. In file mode the program also exits automatically at end of file.

## Notes

### Dynamic resolution & GPU memory

GPU buffers (`d_y`, `d_uv`, `d_bgr`, `d_lab`, `d_mask`, `d_tmp`) are sized to the buffer resolution via `gpu_prepare(ctx, w, h)` in the handoff callback. If the resolution changes (e.g. different file), buffers are freed and reallocated. Example memory for common resolutions:

| Resolution | Y | UV | BGR | Lab | Mask | Tmp | Total |
|------------|-------|-------|-------|-------|-------|-------|-------|
| 4032×3040 | 12 MB | 6 MB | 37 MB | 37 MB | 12 MB | 12 MB | ~116 MB |
| 1920×1080 | 2 MB | 1 MB | 6 MB | 6 MB | 2 MB | 2 MB | ~19 MB |

### Display size in file mode

`--width` still controls the display size (default 1280×960). Larger/smaller files are scaled to fit via the display branch `nvvidconv`. Processing is always at native resolution.

### Morphological mask size

The structuring element is hardcoded as **3×3** in the CUDA kernels:

| Kernel | File:Line | Loop bounds |
|--------|-----------|-------------|
| `kernel_erode3x3` | `seg_kernels.cuh:93` | `dy = [-1, 1]`, `dx = [-1, 1]` |
| `kernel_dilate3x3` | `seg_kernels.cuh:113` | `dy = [-1, 1]`, `dx = [-1, 1]` |

To change to a larger mask (e.g. 5×5), adjust the loop bounds in both kernels:

```c
for (int dy = -2; dy <= 2; dy++)   // was -1..1
    for (int dx = -2; dx <= 2; dx++)
```

The launch helpers `launch_erode3x3` and `launch_dilate3x3` need no changes — they only configure the grid size.

### Recording from file

`nvjpegenc` re-encodes processed frames to MJPEG-AVI. If the file's native framerate exceeds nvjpegenc throughput, the `leaky=downstream` queue drops frames rather than blocking the pipeline.

### Why nvvidconv (not videoconvert) after decodebin

On this platform `decodebin` auto-selects the hardware decoder `nvjpegdec` for MJPEG-AVI, which outputs **NVMM** I420 buffers. The standard `videoconvert` element cannot map NVMM memory → **`not-negotiated`** error from the demuxer. `nvvidconv bl-output=false` handles NVMM input and produces system-memory NV12, matching the identity handoff requirements (same element/caps as the camera path).

### Encoding formats for --input

Tested focus: MJPEG-AVI produced by `chrseg_live --record` (avidemux + nvjpegdec via decodebin). decodebin also handles H.264 MKV (from capture2_x264) and other formats.

## Files

- `chrseg_live_v0_2_0.cu` — main source
- `seg_kernels.cuh` — header-only CUDA kernels
- `CMakeLists.txt` — build config

## Changes from v0.1.8

- `--input <file>` flag for video-file playback
- `gpu_alloc(ctx)` → `gpu_prepare(ctx, w, h)` (dynamic resolution, realloc on change)
- `on_handoff` reads resolution from `GstVideoMeta` (fallback 4032×3040)
- Context: `input_file`, `proc_w/proc_h`, explicit-set flags for camera options
- Camera flags warn-and-ignore in file mode
- Auto-14fps recording framerate gated to camera mode only
- Single GPU-failure warning preserved from v0.1.8