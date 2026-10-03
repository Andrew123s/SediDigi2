# chrseg_live v0.1.4 – Lab colour-space segmentation with custom CUDA kernels

## Overview

GPU-accelerated chromatic segmentation using CUDA 12.6 on Jetson Orin Nano.

**Key difference from v0.1.3:** Segmentation now operates in **CIE Lab colour space** instead
of BGR. Lab separates luminance (L) from chrominance (a, b), making segmentation more
robust to illumination changes. Custom CUDA kernels replace the NPP-based per-channel
thresholding — reducing the GPU call count from 9 NPP operations to 2 CUDA kernels.

- Colour conversion (NV12 → BGR) via NPP (unchanged)
- BGR → Lab via custom CUDA kernel (`kernel_bgr2lab`)
- Foreground mask via combined Lab a+b threshold (`kernel_threshold_ab`)
- Mask applied to Y via custom CUDA kernel (`kernel_apply_mask`)

**No OpenCV dependency.** No morphological operators in this version (planned for v0.1.5).

## Pipeline

```
 nvarguscamerasrc (4032×3040 NVMM)
   → nvvidconv bl-output=false
   → video/x-raw,format=NV12,width=4032,height=3040 (sysmem)
   → identity name=proc
       ↓ [ handoff: NV12 upload → GPU (NV12→BGR→Lab→threshold_ab→mask)
         → mask AND Y → download modified Y + UV=128 ]
   → nvvidconv (scale to display size)
   → video/x-raw(memory:NVMM),width=<display_w>,height=<display_h>
   → nvegltransform → nveglglessink
```

### GPU processing flow (per frame, 4032×3040)

| Step | Kernel / API | Description |
|------|-------------|-------------|
| Upload Y + UV | `cudaMemcpy2D` ×2 | 18 MB host → device |
| NV12 → BGR | `nppiNV12ToBGR_8u_P2C3R` | NPP colour conversion |
| BGR → Lab | `kernel_bgr2lab` | Custom CUDA: sRGB→XYZ→Lab |
| Median a/b | CPU histogram (first frame only) | Background baseline in Lab |
| Threshold a∧b | `kernel_threshold_ab` | Combined a+b range → mask |
| Apply mask | `kernel_apply_mask` | Y &= mask |
| Download Y | `cudaMemcpy2D` + memset UV=128 | 12 MB device → host |

### Comparison with v0.1.3

| | v0.1.3 (BGR) | v0.1.4 (Lab) |
|---|--------------|--------------|
| Colour space | BGR (3 channels) | Lab (L, a, b) |
| GPU kernels for segmentation | 9 NPP calls | 2 CUDA kernels |
| Threshold domain | B/G/R ± delta% | a/b ± delta% |
| Luminance handling | Implicit (B,G,R each carry L) | Explicit (L channel, ignored) |
| Illumination robustness | Low | High (L separated from a/b) |
| Morphology | — (NPP crash) | — (deferred to v0.1.5) |

## Memory

| Buffer | Pitch | Size | Purpose |
|--------|-------|------|---------|
| Y | 4032 | 12 MB | NV12 luma (upload → mask → download) |
| UV | 4032 | 6 MB | NV12 chroma (upload → NV12→BGR) |
| BGR | 12096 | 37 MB | Intermediate (NV12→BGR → BGR→Lab) |
| Lab | 12096 | 37 MB | Lab image (BGR→Lab → threshold) |
| Mask | 4032 | 12 MB | Combined a+b mask (threshold → apply) |
| **Total GPU** | | **~104 MB** | |

All GPU buffers allocated once on first frame. Reduced from 117 MB (v0.1.3) by removing
3 channel-plane buffers and the temp buffer.

## Build

```bash
cmake -S identities -B identities/build
cmake --build identities/build
```

**Prerequisites:** CUDA 12.6, NPP libraries (JetPack / CUDA Toolkit).

## Usage

```bash
./identities/build/chrseg_live_v0_1_4
       [--sensor-id <n>] [--framerate <num/den>]
       [--tnr-mode <0|1|2>] [--tnr-strength <f>]
       [--ee-mode <0|1|2>] [--exposuretime <ns>]
       [--width <n>] [--delta <n>] [--benchmark] [--debug]
```

### Flags

| Flag | Default | Valid | Description |
|------|---------|-------|-------------|
| `--sensor-id` | `0` | `>= 0` | Camera sensor ID |
| `--framerate` | `21/1` | `num/den` | Framerate in Caps |
| `--tnr-mode` | `1` | `0,1,2` | Temporal Noise Reduction |
| `--tnr-strength` | `0.1` | `0.0–1.0` | Only when `--tnr-mode > 0` |
| `--ee-mode` | `0` | `0,1,2` | Edge Enhancement |
| `--exposuretime` | `2500000` | `> 0` | Exposure time in ns |
| `--width` | `1280` | `> 0, % 4` | **Display only** — GPU always at 4032×3040 |
| `--delta` | `10` | `0–100` | Tolerance from median background (%) in Lab a/b |
| `--benchmark` | off | flag | Rolling avg/min/max every 30 frames |
| `--debug` | off | flag | Verbose GPU error messages |

### Example

```bash
./identities/build/chrseg_live_v0_1_4 --delta 15 --exposuretime 47000000 --benchmark
```

Press ENTER or close the preview window to stop.

## Custom CUDA kernels (`seg_kernels.cuh`)

All kernels are defined header-only in `seg_kernels.cuh`. Active in v0.1.4:

| Kernel | Purpose |
|--------|---------|
| `kernel_bgr2lab` | BGR uint8 → Lab uint8 (OpenCV-compatible encoding) |
| `kernel_threshold_ab` | Combined a+b threshold → C1 mask (0x00/0xFF) |
| `kernel_apply_mask` | Y &= mask (in-place) |

Available for v0.1.5 (not called in v0.1.4):

| Kernel | Purpose |
|--------|---------|
| `kernel_erode3x3` | 3×3 erosion (min filter) |
| `kernel_dilate3x3` | 3×3 dilation (max filter) |
| `kernel_threshold_channel` | Single-channel threshold |
| `kernel_and_masks` | AND two C1 masks |
| `kernel_not_mask` | Invert C1 mask |

## Lab colour space

Lab encoding follows OpenCV conventions:
- **L**: [0, 255] — luminance (0 = black, 255 = white)
- **a**: [0, 255] — green (0) ↔ red (255), midpoint 128
- **b**: [0, 255] — blue (0) ↔ yellow (255), midpoint 128

Segmentation uses only the **a** and **b** channels. The delta parameter controls the
threshold range around the first-frame median in both a and b channels simultaneously.

## Differences from v0.1.3

- **Lab colour space** instead of BGR — more robust to lighting changes
- **2 custom CUDA kernels** replace 9 NPP segmentation calls
- **5 GPU buffers** (104 MB) instead of 8 (117 MB)
- **seg_kernels.cuh** — new header-only CUDA kernel library

## Roadmap

- **v0.1.5**: Direct NV12 → Lab kernel (skip BGR intermediate, save 37 MB + NPP call)

## Known Issues

1. **BGR intermediate** — NV12→BGR (NPP) followed by BGR→Lab (CUDA) still requires the 37 MB BGR buffer. Will be eliminated in v0.1.5 with direct NV12→Lab.
2. **First-frame median** — requires downloading full Lab image (37 MB D2H). Could be replaced with GPU histogram in a future version.
3. **GPU memory** — ~104 MB permanently allocated. Reduced from v0.1.3 but still significant.
