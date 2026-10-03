# chrseg_live v0.1.2 – chromatic segmentation live preview (GPU)

## Overview

GPU-accelerated chromatic segmentation using CUDA 12.6 + NVIDIA NPP.

The entire processing pipeline runs on the Jetson Orin Nano GPU:
- Colour conversion (NV12 → BGR) via NPP
- Foreground mask via per-channel inRange(B/G/R) + cross-channel AND
- Mask applied to Y plane via AND → background L=0, foreground L preserved, UV=128

**No OpenCV dependency.** Median background estimation uses a plain-C
histogram scan (only for the first frame).

**Morphology removed** — `nppiErode_8u_C1R` caused a
`CUDA_KERNEL_EXECUTION_ERROR` on Jetson Orin Nano at 4032×3040.
Therefore, the inRange mask is used directly without a previous smoothing.

## NV12 format & colour-space decision

The camera delivers NV12, a YUV 4:2:0 semi-planar format:
- **Y plane**  — luma (brightness), full resolution (4032×3040)
- **UV plane** — chroma (U + V interleaved), half resolution (4032×1520)

Because chroma is subsampled, per-pixel three-channel operations like
`inRange` cannot be applied directly to the native NV12 data.
Three options were considered here:

| Approach | Pro | Contra |
|---|---|---|
| **Y-only threshold** | Native, no conversion | Loses colour information |
| **NV12 → YUV444** | Full YUV per pixel | NPP function not available on this JetPack version |
| **NV12 → BGR** | 1:1 per-channel resolution, NPP function exists | Slight conversion cost |

### Decision: BGR colour space

`nppiNV12ToBGR_8u_P2C3R` is a well-tested NPP primitive. 
BGR provides full-resolution per-pixel data for all three channels. 
The segmentation runs independently on B, G, and R channels and combines the results with a per-pixel AND — equivalent to a three-channel inRange.

## Pipeline

```
 nvarguscamerasrc → nvvidconv (NVMM → sysmem, 4032×3040)
   → identity name=proc
       ↓ [ handoff: NV12 upload → GPU (NV12→BGR→per-channel inRange→AND→NOT→mask)
         → mask AND Y → download modified Y + UV=128 ]
   → nvvidconv (sysmem → NVMM, scale to display size)
   → nvegltransform → nveglglessink
```

### GPU processing flow (per frame)

| Step | API | Time (est.) |
|------|-----|-------------|
| Upload Y + UV (18 MB) | `cudaMemcpy2D` | ~2 ms |
| NV12 → BGR | `nppiNV12ToBGR_8u_P2C3R` | ~0.5 ms |
| BGR → 3 planes | `nppiCopy_8u_C3P3R` | ~0.3 ms |
| Per-channel inRange (B, G, R) | `nppiCompareC_8u_C1R` (×6) + `nppiAnd_8u_C1R` (×3) | ~0.5 ms |
| Combine channels + invert | `nppiAnd_8u_C1R` (×2) + `nppiNot_8u_C1R` | ~0.2 ms |
| Mask AND Y + download | `nppiAnd_8u_C1R` + `cudaMemcpy2D` | ~1.5 ms |
| **Total GPU** | | **~5 ms** (~200 fps) |

## Build

```bash
cmake -S identities -B identities/build
cmake --build identities/build
```

**Prerequisites:** CUDA 12.6, NPP libraries (part of JetPack / CUDA Toolkit).

## Usage

```bash
./identities/build/chrseg_live_v0_1_2
       [--sensor-id <n>] [--framerate <num/den>]
       [--tnr-mode <0|1|2>] [--tnr-strength <f>]
       [--ee-mode <0|1|2>] [--exposuretime <ns>]
       [--width <n>] [--delta <n>] [--benchmark] [--debug]
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
| `--benchmark` | off | flag | Print rolling avg/min/max frame time every 30 frames |
| `--debug` | off | flag | Verbose GPU error messages |

### Example

```bash
./identities/build/chrseg_live_v0_1_2 --delta 15 --exposuretime 47000000 --benchmark
```

Press ENTER or close the preview window to stop.

## Differences from v0.1.1

- **GPU acceleration**: all pixel processing on GPU
- **No OpenCV**: completely removed as a dependency; median uses plain C histogram
- **Benchmark precision**: frame times stored as `double` (vs `gint64` truncation in v0.1.1)
- **BGR three-channel segmentation**: NV12→BGR instead of NV12→BGR→Lab; segmentation on all three B/G/R channels independently, combined with AND — retains full colour information
- **Simplified NPP pipeline**: replaced the 7-call Lab-inRange chain with `CompareC` + `And` primitives (3× per channel + 2× cross-channel)
- **GPU memory**: ~117 MB (Y + UV + BGR + 3 planes + tmp + mask), still less than the 128 MB of the initial Lab pipeline thanks to removed tmp2/p0/p1/p2 intermediates
- **Morphology removed**: `nppiErode_8u_C1R` crashed unexpectedly with `CUDA_KERNEL_EXECUTION_ERROR` on Jetson Orin Nano at 4032×3040; the raw mask is used without smoothing

## Memory

| Buffer | Size | Location |
|--------|------|----------|
| Y | 4032×3040 = 12 MB | host + GPU |
| UV | 4032×1520 = 6 MB | host + GPU |
| BGR | 4032×3040×3 = 37 MB | GPU only |
| Plane B | 4032×3040 = 12 MB | GPU only (reused as B-mask after threshold) |
| Plane G | 4032×3040 = 12 MB | GPU only (reused as G-mask) |
| Plane R | 4032×3040 = 12 MB | GPU only (reused as R-mask) |
| Tmp | 4032×3040 = 12 MB | GPU only |
| Mask | 4032×3040 = 12 MB | GPU only |
| **Total GPU** | **~117 MB** | |

All GPU buffers allocated once on first frame; freed on exit.

## Known Issues

1. **Morphology crash** — `nppiErode_8u_C1R` raises `CUDA_KERNEL_EXECUTION_ERROR` on Jetson Orin Nano at full resolution (4032×3040). Morphological operations are disabled; the raw mask is used directly.

2. **BGR vs LAB colour space** — Unlike v0.1.0/v0.1.1 which used OpenCV's BGR→Lab conversion, this version thresholds directly in BGR. The median is computed from the B/G/R channels of the first frame. Tune `--delta` accordingly if migrating from the Lab-based pipeline.

3. **nvvidconv stride padding** — `nvvidconv` may add row-alignment padding, making the buffer stride larger than the image width. The code reads `GstVideoMeta` from the buffer to obtain the actual stride and UV offset. Falls back to `stride = width` if metadata is absent.
