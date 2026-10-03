# chrseg_live v0.1.5

Chromatic segmentation live preview with Motion JPEG recording.

## What's new in v0.1.5

- `--record` flag for hardware-accelerated Motion JPEG recording
- `--record-file <filename>` to specify output path (default: `chrseg_YYYYMMDD_HHMMSS` in ~/Videos)
- Recording branch uses `nvjpegenc` (HW JPEG via VIC) + `avimux` → `filesink`
- Pipeline uses GStreamer `tee` to split GPU-modified NV12 to both display and recording branches
- No `videoconvert` needed — nvjpegenc accepts NV12 from GPU memory directly

## Architecture

Camera → nvarguscamerasrc (NVMM) → nvvidconv → identity (sysmem) → **tee**

- **Display branch:** nvvidconv → nvegltransform → nveglglessink
- **Recording branch:** nvjpegenc → avimux → filesink

GPU processing (~42 ms) is applied once per frame via the identity element. Both branches receive the same GPU-modified NV12 buffer with zeroed background. UV channels remain untouched.

## Recording benchmarks

| Encoder | Type | FPS | % of camera rate |
|---------|------|-----|------------------|
| nvjpegenc | HW (VIC) | ~14.3 | 68% |
| x264enc ultrafast | SW (libx264) | ~11.6 | 55% |
| openh264enc | SW | ~9.4 | 45% |

Recording reduces display frame rate from ~24 fps (display-only) to ~14 fps (with recording) when using nvjpegenc. Frames that exceed the encoder throughput are dropped.

## Build

```bash
cd /home/dev/SediDigi/capture/cpp/identities
cmake --build build --target chrseg_live_v0_1_5
```

## Usage

```bash
# Display only (no recording)
./build/chrseg_live_v0_1_5

# Display + recording with default filename
./build/chrseg_live_v0_1_5 --record

# Display + recording to specific file
./build/chrseg_live_v0_1_5 --record /tmp/<ziel>

# Full options
./build/chrseg_live_v0_1_5 --record <ziel> \
    --delta 10 --exposuretime 2500000 \
    --framerate 21/1 --benchmark

# Original image without Y channel masking
./build/chrseg_live_v0_1_5 --no-mask
```

## Command-line options

| Option | Default | Description |
|--------|---------|-------------|
| `--record [file]` | off | Enable recording; optional output filename |
| `--record-file <file>` | `~/Videos/chrseg_<timestamp>` | Output file (if no file after --record) |
| `--sensor-id <n>` | 0 | Camera sensor ID |
| `--framerate <n/d>` | 21/1 | Camera framerate |
| `--tnr-mode <0\|1\|2>` | 1 | Temporal noise reduction mode |
| `--tnr-strength <f>` | 0.1 | TNR strength (0.0–1.0, requires tnr-mode > 0) |
| `--ee-mode <0\|1\|2>` | 0 | Edge enhancement mode |
| `--exposuretime <ns>` | 2500000 | Exposure time in nanoseconds |
| `--width <n>` | 1280 | Display width (4:3 ratio) |
| `--delta <n>` | 10 | Chromatic segmentation threshold % (0–100) |
| `--no-mask` | off | Skip Y channel masking; display/recording shows original image |
| `--benchmark` | off | Print 30-frame average timing |
| `--debug` | off | Enable GStreamer debug |

## Controls

- Press **ENTER** or **close the window** to stop
- Recording is automatically saved on stop

## Known Issues

### Frame dropping with `--record` is uncoordinated

When recording is enabled, both the display and recording branches share a `tee` element. The recording branch uses `queue leaky=downstream max-size-buffers=1 ! nvjpegenc ! avimux ! filesink`. When `nvjpegenc` cannot keep up (~14 fps vs. camera 21 fps), frames are dropped gracefully by the leaky queue without blocking the display branch.

**Workaround:** Reduce camera framerate to match encoder throughput for minimal frame drops:
```bash
./build/chrseg_live_v0_1_5 --record --framerate 14/1
```

**Planned enhancement (v0.1.6):** Optionally add `--framerate` as a configurable parameter for the recording branch.

## GPU pipeline

Based on v0.1.4, with fix: UV channels are no longer overwritten with neutral gray.

1. NV12 upload to GPU
2. NV12 → BGR conversion (NPP)
3. BGR → Lab conversion (custom CUDA kernel)
4. Median background from first frame
5. Combined Lab a/b threshold (custom CUDA kernel)
6. Mask inversion (custom CUDA kernel)
7. Apply mask to Y channel (custom CUDA kernel)
8. Download modified Y to host buffer (UV untouched)

## Files

- `chrseg_live_v0_1_5.cu` — main source
- `seg_kernels.cuh` — header-only CUDA kernels
- `CMakeLists.txt` — build config

## Dependencies

- GStreamer 1.0
- GStreamer plugins: nvarguscamerasrc, nvvidconv, nvegltransform, nveglglessink, nvjpegenc, avimux, filesink
- CUDA / NPP (Jetson Orin Nano, JetPack R36.5.0)

## Notes

### Available encoders on Jetson Orin Nano (JetPack R36.5.0)

**Hardware-accelerated:**

| Element | Type | Status |
|---------|------|--------|
| `nvjpegenc` | JPEG (VIC) | Available — only HW encoder on Orin Nano |
| `nvv4l2h264enc` | H.264 (NVENC) | **Not available** — `libnvidia-encode.so` missing |
| `nvv4l2h265enc` | H.265 (NVENC) | **Not available** — `libnvidia-encode.so` missing |

The `nvcodec` GStreamer plugin exists but registers 0 features because the NVENC library is absent. Only Orin NX and AGX Orin have NVENC hardware.

**Software encoders (CPU-based):**

| Element | Library | Type |
|---------|---------|------|
| `x264enc` | libx264 | H.264 |
| `x265enc` | libx265 | H.265 |
| `openh264enc` | OpenH264 | H.264 |
| `vp8enc` / `vp9enc` | libvpx | VP8 / VP9 |
| `av1enc` | libaom | AV1 |

`nvjpegenc` is the only viable option for hardware-accelerated video recording on this system.
