# capture2_x264.cpp – Software-Encoding Fallback (x264enc)

## Background

On Jetson Orin Nano (L4T 36.5.0 / JetPack 6.2.2), the hardware encoder `nvv4l2h264enc` is **not available** because the Orin Nano lacks the NVENC hardware engine. The only H.264 encoder available is `x264enc` (software x264 on ARM CPU).

This file is a drop-in replacement for `capture2.cpp` that replaces `nvv4l2h264enc` with `x264enc`.

## Overview

| | capture2.cpp | capture2_x264.cpp |
|---|---|---|
| **Encoding** | H.264 (HW `nvv4l2h264enc`) | H.264 (SW `x264enc`) |
| **Bitrate unit** | bit/sec | kbit/sec |
| **NVMM → System Memory** | not needed (HW encoder accepts NVMM directly) | once before `tee` via `nvvidconv` (single conversion for all branches) |
| **CPU load** | minimal (hardware offload) | high (software encoding 190 Mpx/s @ 4032×3040×21 fps) |
| **Tee branches** | 3 (preview + fullres + downsampled) | same structure |
| **Framerate** | Always in caps (default 21/1) | same |
| **Extra CLI flags** | `--sensor-id`, `--framerate`, `--tnr-mode`, `--tnr-strength`, `--ee-mode` | same |

## Dependencies

- GStreamer 1.20.3 (`gstreamer-1.0`, `gstreamer-app-1.0`, `gstreamer-video-1.0`)
- NVIDIA GStreamer plugins (JetPack / `nvidia-l4t-gstreamer`)
- CMake 3.22.1
- g++ 11.4.0
- `x264enc` (provided by `gstreamer1.0-plugins-ugly` or preinstalled on JetPack)

## Files

| File | Description |
|---|---|
| `capture2_x264.cpp` | Main source file |
| `CMakeLists.txt` | CMake build configuration (Target `capture2_x264`) |

## Build

```bash
mkdir -p build
cmake -S . -B build
cmake --build build
```

## Usage

```bash
./build/capture2_x264 <recording-name>
       [--sensor-id <n>] [--framerate <num/den>]
       [--tnr-mode <0|1|2>] [--tnr-strength <f>]
       [--ee-mode <0|1|2>]
```

| Flag | Default | Valid values | Description |
|---|---|---|---|
| `<recording-name>` | – | any string | Directory name under `/home/dev/Videos/` |
| `--sensor-id` | `0` | `>= 0` | Camera sensor ID |
| `--framerate` | `21/1` | `num/den` with `num > 0, den > 0` | Override the default 21/1 framerate |
| `--tnr-mode` | `1` | `0, 1, 2` | Temporal Noise Reduction |
| `--tnr-strength` | `0.1` | `0.0 – 1.0` | Only valid when `--tnr-mode > 0` |
| `--ee-mode` | `0` | `0, 1, 2` | Edge Enhancement |

Examples:

```bash
./build/capture2_x264 test01
./build/capture2_x264 --tnr-mode 2 --tnr-strength 0.5 test01
./build/capture2_x264 --framerate 30/1 --ee-mode 1 test01
```

Optional flags can appear in any order before or after the recording name.

Remark: No matter which port the camera is connected to, it can always be accessed under sensor ID 0.
This makes the flag `--sensor-id` unnecessary, at least for the current configuration.

## Implementation Details

### GStreamer Pipeline

The key difference from `capture2.cpp` is that `x264enc` does not accept NVMM input, so an `nvvidconv` converts from NVMM to system memory **once** before the `tee`. All three branches then operate in system memory. Bitrate values are in kbit/sec (80000 kbit/s ≈ 80 Mbps, 20000 kbit/s ≈ 20 Mbps).

```
nvarguscamerasrc
  (sensor-id=<n>, tnr-mode=<n>[, tnr-strength=<f>], ee-mode=<n>,
   awblock=true, aelock=true, saturation=1)
  → caps: video/x-raw(memory:NVMM), width=4032, height=3040[, framerate=<num>/<den>], format=NV12
  → nvvidconv bl-output=false
  → caps: video/x-raw, format=NV12, width=4032, height=3040[, framerate=<num>/<den>]
  → tee name=t
     ├→ Branch A (preview)
     │   t. → queue(max-size-buffers=1, leaky=downstream)
     │       → videoscale → caps: video/x-raw, 1280×960
     │       → videoconvert → ximagesink sync=false
     ├→ Branch B (full resolution recording)
     │   t. → queue(max-size-buffers=5, max-size-bytes=0, max-size-time=0)
     │       → x264enc bitrate=80000 speed-preset=1 qos=false
     │       → matroskamux
     │       → filesink (fullres.mkv)
     └→ Branch C (downsampled recording)
         t. → queue(max-size-buffers=10, max-size-bytes=0, max-size-time=0)
             → videoscale → caps: video/x-raw, 1008×760
             → x264enc bitrate=20000 speed-preset=1 qos=false
             → matroskamux
             → filesink (downsampled.mkv)
```

### Performance Considerations

Each NVMM frame at 4032×3040 (~18 MB) is copied from GPU to system memory once via `nvvidconv` before the `tee`. The encoding branches set `max-size-bytes=0 max-size-time=0` so only `max-size-buffers` limits the queue depth (same as `capture2.cpp`).

`speed-preset=1` corresponds to `ultrafast` — the fastest x264 preset. This is necessary to achieve real-time encoding at 4032×3040 × 21 fps (~190 Mpx/s) on a Jetson Orin Nano CPU.

### Other Details

Command-line argument parsing, ENTER-key detection, signal handling, bus monitoring, and directory creation are identical to `capture2.cpp`.
