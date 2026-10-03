# chrseg_live v0.1.7

Chromatic segmentation live preview with morphological noise removal.

## What's new in v0.1.7

- **Morphological opening** (erode → dilate) on binary mask after threshold, which removes "salt-and-pepper" noise and closes small gaps
- Toggle with `--no-morph` flag

## Architecture

**GPU pipeline (per frame):**

```
upload NV12
  → [NPP] NV12→BGR
  → [CUDA] BGR→Lab
  → [CPU] median a/b (first frame only)
  → [CUDA] threshold_ab → not_mask
  → [CUDA] erode (d_tmp) → dilate (d_mask)    ← new in v0.1.7
  → [CUDA] apply_mask to Y
  → download modified Y (UV keeps untouched)
```

**Full pipeline (record mode):**

```
nvarguscamerasrc ... framerate=14/1
  → nvvidconv → identity(name=proc)
  → tee name=t
    t. → queue leaky=downstream max-size-buffers=2
       → nvvidconv → nvegltransform → nveglglessink
    t. → queue leaky=downstream max-size-buffers=1
       → nvvidconv → nvjpegenc → avimux → filesink
```

## CLI flags

| Option | Default | Description |
|--------|---------|-------------|
| `--record [file]` | off | Enable recording; auto-sets 14 fps |
| `--no-mask` | off | Skip Y channel masking (original image) |
| `--no-morph` | off | Disable morphological opening |
| `--sensor-id <n>` | 0 | Camera sensor ID |
| `--framerate <n/d>` | 21/1 or 14/1 | Camera framerate (auto 14/1 with `--record`) |
| `--tnr-mode <0\|1\|2>` | 1 | Temporal noise reduction |
| `--tnr-strength <f>` | 0.1 | TNR strength (0.0–1.0) |
| `--ee-mode <0\|1\|2>` | 0 | Edge enhancement |
| `--exposuretime <ns>` | 2500000 | Exposure time |
| `--width <n>` | 1280 | Display width (4:3) |
| `--delta <n>` | 10 | Threshold % (0–100) |
| `--benchmark` | off | 30-frame timing stats |
| `--debug` | off | GStreamer debug |

## Build

```bash
cmake -S identities -B identities/build && cmake --build identities/build --target chrseg_live_v0_1_7
```

## Usage

```bash
# Display only (21 fps, morphology on)
./build/chrseg_live_v0_1_7

# With recording (auto 14 fps, morphology on)
./build/chrseg_live_v0_1_7 --record

# Disable morphology
./build/chrseg_live_v0_1_7 --no-morph

# Disable both mask and morphology
./build/chrseg_live_v0_1_7 --no-mask --no-morph

# Full options
./build/chrseg_live_v0_1_7 --record --delta 15 --benchmark
```

## GPU memory

| Buffer | Size | Purpose |
|--------|------|---------|
| `d_y` | 12 MB | NV12 Y plane |
| `d_uv` | 6 MB | NV12 UV plane |
| `d_bgr` | 37 MB | BGR conversion |
| `d_lab` | 37 MB | Lab conversion |
| `d_mask` | 12 MB | Binary mask |
| `d_tmp` | 12 MB | Morphology intermediate |
| **Total** | **~116 MB** | |

## Files

- `chrseg_live_v0_1_7.cu` — main source
- `seg_kernels.cuh` — header-only CUDA kernels
- `CMakeLists.txt` — build config

## Notes

### Morphological mask size

The structuring element is hardcoded with 3×3 size in the CUDA kernels:

| Kernel | File:Line | Loop bounds |
|--------|-----------|-------------|
| `kernel_erode3x3` | `seg_kernels.cuh:93` | `dy = [-1, 1]`, `dx = [-1, 1]` |
| `kernel_dilate3x3` | `seg_kernels.cuh:113` | `dy = [-1, 1]`, `dx = [-1, 1]` |

To change to a larger mask (e.g. 5×5), adjust the loop bounds in both kernels:

```c
for (int dy = -2; dy <= 2; dy++)   // was -1..1
    for (int dx = -2; dx <= 2; dx++)
```

The launch helpers `launch_erode3x3` and `launch_dilate3x3` in the same file need no changes — they only configure the grid size. Remark: Larger masks remove more noise but also erode fine details.

### Performance

| Step | Time (4032×3040) |
|------|-----------------|
| NV12 upload | ~8 ms |
| NV12→BGR (NPP) | ~9 ms |
| BGR→Lab (CUDA) | ~7 ms |
| threshold + not | ~3 ms |
| **erode + dilate** | **~1–2 ms** |
| apply + download | ~8 ms |
| **Total** | **~36–37 ms** |

### Dependencies

- GStreamer 1.0
- GStreamer plugins: nvarguscamerasrc, nvvidconv, nvegltransform, nveglglessink, nvjpegenc, avimux
- CUDA / NPP (Jetson Orin Nano, JetPack R36.5.0)

### Changes from v0.1.6

- Morphological opening (erode→dilate) after threshold
- New GPU buffer `d_tmp` (+12 MB) for intermediate mask
- `--no-morph` flag to disable morphology
- `ctx.morph` and `gboolean morph` in context struct
