# chrseg_live v0.1.6

Chromatic segmentation live preview with stable Motion JPEG recording.

## What's new in v0.1.6

- **Auto-framerate for recording:** When `--record` is used without explicit `--framerate`, camera automatically sets to 14 fps to match nvjpegenc throughput. Display-only mode remains at 21 fps.
- **Display queue leaky:** Both tee branches now use `leaky=downstream` to prevent pipeline freeze when either display or recording stalls.
- Eliminates the "one frame then freeze" issue from v0.1.5 caused by nvjpegenc backpressure.

## Architecture

Camera → nvarguscamerasrc (NVMM) → nvvidconv → identity (sysmem) → **tee**

- **Display branch:** `queue leaky=downstream max-size-buffers=2` → nvvidconv → nvegltransform → nveglglessink
- **Recording branch:** `queue leaky=downstream max-size-buffers=1` → nvvidconv → nvjpegenc → avimux → filesink

GPU processing (~42 ms) is applied once per frame via the identity element. Both branches receive the same GPU-modified NV12 buffer. UV channels remain untouched.

## Framerate behavior

| Mode | Default framerate | Override with `--framerate` |
|------|-------------------|----------------------------|
| Display only | 21/1 | Yes |
| `--record` | **14/1** (auto) | Yes |

The auto-adjustment ensures nvjpegenc can encode every frame without backpressure. If you pass `--framerate 21/1 --record`, the pipeline will attempt 21 fps recording (may drop frames).

## Build

```bash
cd /home/dev/SediDigi/capture/cpp/identities
cmake --build build --target chrseg_live_v0_1_6
```

## Usage

```bash
# Display only (21 fps)
./build/chrseg_live_v0_1_6

# Display + recording (auto 14 fps)
./build/chrseg_live_v0_1_6 --record

# Display + recording to specific file
./build/chrseg_live_v0_1_6 --record /tmp/<record filename>

# Recording with explicit framerate override
./build/chrseg_live_v0_1_6 --record --framerate 14/1

# Full options
./build/chrseg_live_v0_1_6 --record <record filename> \
    --delta 10 --exposuretime 2500000 \
    --framerate 14/1 --benchmark

# Original image without Y channel masking
./build/chrseg_live_v0_1_6 --no-mask
```

## Command-line options

| Option | Default | Description |
|--------|---------|-------------|
| `--record [file]` | off | Enable recording; auto-sets 14 fps unless `--framerate` given |
| `--record-file <file>` | `~/Videos/chrseg_<timestamp>` | Output file (if no file after --record) |
| `--sensor-id <n>` | 0 | Camera sensor ID |
| `--framerate <n/d>` | 21/1 (display) / 14/1 (record) | Camera framerate; overrides auto-detection |
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

## GPU pipeline

1. NV12 upload to GPU
2. NV12 → BGR conversion (NPP)
3. BGR → Lab conversion (custom CUDA kernel)
4. Median background from first frame
5. Combined Lab a/b threshold (custom CUDA kernel)
6. Mask inversion (custom CUDA kernel)
7. Apply mask to Y channel (custom CUDA kernel)
8. Download modified Y to host buffer (UV untouched)

## Files

- `chrseg_live_v0_1_6.cu` — main source
- `seg_kernels.cuh` — header-only CUDA kernels
- `CMakeLists.txt` — build config

## Dependencies

- GStreamer 1.0
- GStreamer plugins: nvarguscamerasrc, nvvidconv, nvegltransform, nveglglessink, nvjpegenc, avimux, filesink
- CUDA / NPP (Jetson Orin Nano, JetPack R36.5.0)

## Notes

### Encoder limitations

`nvjpegenc` is the only HW encoder on Orin Nano (JetPack R36.5.0). Max throughput: ~14 fps at 4032×3040. No NVENC available (`libnvidia-encode.so` missing).

### Changes from v0.1.5

- Auto-framerate 14/1 when recording (was: manual `--framerate 14/1` required)
- Display queue now uses `leaky=downstream` (was: plain `queue`, caused freeze)
- Recording branch adds `nvvidconv` before `nvjpegenc` (sysmem → NVMM required for HW JPEG encoding)
- Both tee branches are now non-blocking
