# chrseg_live v0.1.8

Chromatic segmentation live preview with morphological noise removal.

## What's new in v0.1.8

- **Single GPU-failure warning:** The warning `GPU processing skipped (ok=FALSE)` is now printed at most once instead of once per frame.
- **Fixed `--no-mask` spam:** Previously `--no-mask` triggered the warning on every frame because masking is intentionally disabled. Now no warning is shown in that case.

## Build

```bash
cmake -S identities -B identities/build && cmake --build identities/build --target chrseg_live_v0_1_8
```

## Usage

```bash
# Display only (21 fps)
./build/chrseg_live_v0_1_8

# With recording (auto 14 fps)
./build/chrseg_live_v0_1_8 --record

# Disable morphology
./build/chrseg_live_v0_1_8 --no-morph

# Disable masking (no warning in v0.1.8)
./build/chrseg_live_v0_1_8 --no-mask
```

All command-line options are identical to v0.1.7 (`--sensor-id`, `--framerate`, `--tnr-mode`, `--tnr-strength`, `--ee-mode`, `--exposuretime`, `--width`, `--delta`, `--no-mask`, `--no-morph`, `--record`, `--benchmark`, `--debug`).

## Changes from v0.1.7

- Added `gboolean warned_gpu_fail` to `ChrSegContext`
- Warning condition changed from `ctx->first_frame == FALSE` to `!ctx->no_mask && !ctx->warned_gpu_fail`
- `warned_gpu_fail` is set to `TRUE` after the first warning to suppress repeats

## GPU pipeline

Identical to v0.1.7:

```
upload NV12 → [NPP] NV12→BGR → [CUDA] BGR→Lab
  → [CPU] median a/b (first frame)
  → [CUDA] threshold_ab → not_mask
  → [CUDA] erode → dilate (opening)
  → [CUDA] apply_mask to Y
  → download modified Y
```

## Notes

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

## Files

- `chrseg_live_v0_1_8.cu` — main source
- `seg_kernels.cuh` — header-only CUDA kernels
- `CMakeLists.txt` — build config