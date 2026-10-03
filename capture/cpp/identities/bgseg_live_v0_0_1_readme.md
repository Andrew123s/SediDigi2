# bgseg_live v0.0.1

Live segmentation by background differentiation, 
for ArduCam camera and unprocessed video files.

Contrary to the chromatic approach (chrseg_live), the background is not modelled
by a colour statistic: first frame is frozen as the background image, 
every later frame is compared against it pixelwise in Lab space. 
A pixel is classified as object when at least one Lab channel deviates
from the frozen background value by more than the `--delta` threshold.

## Background model

- The very first frame (camera: after startup; file: first frame) is captured
  to a GPU-side Lab copy `d_bg_lab` and never updated again (static model).
- Scene changes that alter the whole background (lighting, exposure/Gain drift,
  camera movement) produce false positives.

## Classification rule

Measured per pixel, byte domain (L, a, b as produced by `kernel_bgr2lab`):

```
t = round(255 * delta / 100)   (delta float, default 10.0 → t = 26; delta=2.5 → t = 6)

object  ⟺  |ΔL| > t  OR  |Δa| > t  OR  |Δb| > t
```

Mask semantics: `0xFF` = object, `0x00` = background. After the morphological
opening (erode → dilate, removes single-pixel noise) the mask is applied to the
**Y channel only** (UV untouched, same as chrseg): background renders black
(subject to the same NV12 chroma-ghost — see Notes), objects keep their full
colour.

## GPU pipeline (per frame)

```
upload NV12
  → [NPP] NV12→BGR
  → [CUDA] BGR→Lab
  → first frame: copy Lab → background model (d_bg_lab)
  → [CUDA] bg-diff mask   (|ΔL|>t OR |Δa|>t OR |Δb|>t)
  → [CUDA] erode → dilate (opening)
  → [CUDA] apply_mask to Y
  → download modified Y (UV untouched)
```

No median/histogram step (unlike chrseg) — median colour statistics are not used.

## CLI flags

| Option | Default | Description |
|--------|---------|-------------|
| `--input <file>` | camera | Read from video file instead of camera |
| `--record [file]` | off | Enable recording (re-encode via nvjpegenc) |
| `--no-mask` | off | Skip background masking (original image) |
| `--no-morph` | off | Disable morphological opening |
| `--sensor-id <n>` | 0 | Camera sensor ID (ignored in file mode) |
| `--framerate <n/d>` | 21/1 | Camera framerate (ignored in file mode) |
| `--tnr-mode <0\|1\|2>` | 1 | TNR (ignored in file mode) |
| `--tnr-strength <f>` | 0.1 | TNR strength (ignored in file mode) |
| `--ee-mode <0\|1\|2>` | 0 | Edge enhancement (ignored in file mode) |
| `--exposuretime <ns>` | 2500000 | Exposure (ignored in file mode) |
| `--width <n>` | 1280 | Display width (4:3) |
| `--delta <n.n>` | 10.0 | Threshold % (0.0–100.0, float) → t = round(255·delta/100) per Lab channel |
| `--benchmark` | off | 30-frame timing stats |
| `--debug` | off | GStreamer debug |

Source pipeline (camera/file), recording branch (auto 14 fps camera mode), file
preroll and stdin/window/EOS handling are identical to chrseg_live v0.2.1.

## Build

```bash
cmake -S identities -B identities/build && cmake --build identities/build --target bgseg_live_v0_0_1
```

## Usage

```bash
# Camera, background = first frame
./build/bgseg_live_v0_0_1

# Camera with tighter tolerance (float, fractional steps possible)
./build/bgseg_live_v0_0_1 --delta 2.5

# Video file (first frame of the clip = background)
./build/bgseg_live_v0_0_1 --input <video filename>

# Unmasked original for comparison
./build/bgseg_live_v0_0_1 --input <video filename> --no-mask

# Benchmark GPU pipeline
./build/bgseg_live_v0_0_1 --input <video filename> --benchmark
```

Press ENTER or close the window to stop. In file mode the program exits
automatically at end of file.

## Notes

### Dynamic resolution

GPU buffers (incl. the background model `d_bg_lab`) are sized to the buffer
resolution; on a resolution change the background is re-captured (`first_frame`
is reset). Memory @4032×3040: Y 12 + UV 6 + BGR 37 + Lab 37 + BG-Lab 37 + Mask 12
+ Tmp 12 = ~153 MB.

### Static background — practical caveats

- **Camera noise/gain drift** or exposure changes shift the whole Lab image →
  widespread false positives. The fixed exposure (`exposuretime` 2.5 ms,
  AELock) keeps this low in steady conditions.
- **Lighting changes** (clouds, artificial light) are detected as foreground.
- **Shadows** of objects deviate in L → count as foreground objects (no shadow
  handling in v0.0.1).
- **delta as density**: at `--delta 10.0` a pixel must stay within ±26 Lab bytes
  of the frozen background — moderate sensor noise is tolerated, real objects
  clearly exceed it. Fractional values (e.g. `--delta 2.5`) allow finer tuning.

### Chroma ghost and playback

Only Y is masked (0), UV keeps the background chroma — the recorded stream looks
exactly like a chrseg recording. Consequently the **seg_play** utility (Y==0
→ black, else original colour) plays bgseg recordings without changes.

### Morphology

Opening (3×3 erode then 3×3 dilate) removes isolated noise pixels from the mask.
Disable with `--no-morph` if the response feels too eroded.

## Files

- `bgseg_live_v0_0_1.cu` — main source
- `seg_kernels.cuh` — added `kernel_bgdiff_lab` + `launch_bgdiff_lab` (additive)
- `CMakeLists.txt` — build config (target `bgseg_live_v0_0_1`)