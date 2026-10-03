# capture2.cpp – C++ Implementation of denoise_capture.sh

## TODO
On SediDigi2, the hardware encoder nvv4l2h264enc is not available anymore, also checked via
```
gst-inspect-1.0 nvv4l2h264enc >/dev/null 2>&1 && echo "installed" || echo "not installed"
```
Therefore, `capture2` in the current version is not working. 
Using a software decoder like x264enc is the only option, see also
[this forum entry.](https://forums.developer.nvidia.com/t/nvenc-nvv4l2h264enc-nvv4l2h265enc-missing-on-jetson-orin-nano-with-jetpack-6-2-deepstream-7-1/353808)

## Overview

C++ port of `denoise_capture.sh`. Comparison to `capture.cpp`:

| | capture.cpp | capture2.cpp |
|---|---|---|
| **Source script** | `capture.sh` | `denoise_capture.sh` |
| **TNR** | `tnr-mode=0` (off) | `tnr-mode=1`, `tnr-strength=0.1` |
| **Encoding** | JPEG → AVI | H.264 (`nvv4l2h264enc`) → MP4 (`qtmux`) |
| **Output** | 1 file: `<name>` | Folder `<name>/` with 2 files |
| **Tee branches** | 2 (record + preview) | 3 (preview + fullres + downsampled) |
| **Framerate** | Always 21/1 in caps | Only when `--framerate` is set |
| **Extra CLI flags** | `--sensor-id`, `--framerate` | + `--tnr-mode`, `--tnr-strength`, `--ee-mode` |

## Dependencies

- GStreamer 1.20.3 (`gstreamer-1.0`, `gstreamer-app-1.0`, `gstreamer-video-1.0`)
- NVIDIA GStreamer plugins (JetPack / `nvidia-l4t-gstreamer`)
- CMake 3.22.1
- g++ 11.4.0

All libraries are preinstalled on the system, no additional installation was required.

## Files

| File | Description |
|---|---|
| `capture2.cpp` | Main source file |
| `CMakeLists.txt` | CMake build configuration (Target `capture2`) |

## Build

```bash
mkdir -p build
cmake -S . -B build
cmake --build build
```

## Usage

```bash
./build/capture2 <recording-name>
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
./build/capture2 test01
./build/capture2 --tnr-mode 2 --tnr-strength 0.5 test01
./build/capture2 --framerate 30/1 --ee-mode 1 test01
```

Optional flags can appear in any order before or after the recording name.

Remark: No matter which port the camera is connected to, it can always be accessed under sensor ID 0.
This makes the flag `--sensor-id` unnecessary, at least for the current configuration.

## Implementation Details

### Command-line arguments

A `Config` struct holds all parsed values; defaults are defined as a static const instance. Arguments are parsed in a loop over `argv[1..]` via `strcmp()` – order is arbitrary. After parsing, a post-validation step rejects `--tnr-strength` when `tnr-mode == 0`.

### GStreamer Pipeline

The pipeline is built dynamically using `GString`: conditional parts (TNR strength, framerate caps) are appended via `if` statements, the rest is fixed.

Each NVMM frame at 4032×3040 is ~18 MB, exceeding the default `max-size-bytes` (10 MB) of a GStreamer queue. The encoding branches therefore set `max-size-bytes=0 max-size-time=0` so only `max-size-buffers` limits the queue depth.

```
nvarguscamerasrc
  (sensor-id=<n>, tnr-mode=<n>[, tnr-strength=<f>], ee-mode=<n>,
   gainrange="1 1", ispdigitalgainrange="1 1",
   exposuretimerange="2500000 2500000", wbmode=4,
   awblock=true, aelock=true, saturation=1)
  → caps: video/x-raw(memory:NVMM), width=4032, height=3040[, framerate=<num>/<den>]
  → tee
     ├→ Branch A – queue(max-size-buffers=1, leaky=downstream)
     │              → nvvidconv → caps: video/x-raw(NVMM), 1280×960
     │              → nvegltransform → nveglglessink (preview)
      ├→ Branch B – queue(max-size-buffers=50, max-size-bytes=0, max-size-time=0, leaky=0)
      │              → nvv4l2h264enc bitrate=80000000 → h264parse → qtmux
      │              → filesink (fullres.mp4)
      └→ Branch C – queue(max-size-buffers=30, max-size-bytes=0, max-size-time=0, leaky=0)
                     → nvvidconv → caps: video/x-raw(NVMM), 1008×760
                     → nvv4l2h264enc bitrate=20000000 → h264parse → qtmux
                     → filesink (downsampled.mp4)
```

### Enter-key / stdin Detection

A `GIOChannel` watch on `STDIN_FILENO` monitors for the ENTER key. When pressed, `stop_recording()` sends an EOS event to the pipeline. The watch auto-removes after the first trigger (callback returns `FALSE`).

### Signal Handling

A `volatile gboolean running` flag prevents the `SIGINT` handler from accessing the pipeline after it has been freed (solves a race when Ctrl+C is pressed after the pipeline already shut down).

### Bus Monitoring

The bus watch callback handles:

- **EOS** → quits the main loop
- **`"Output window was closed"`** → treated as normal termination (no error message)
- **Other errors** → printed to stderr + quits the main loop

### Directory Creation

The output directory `/home/dev/Videos/<name>/` is created at startup via `mkdir()` with `0755` permissions, matching the original script's `mkdir -p` behavior.

### Error Handling

The error handling is minimal:

- Missing argument → usage message + exit code 1
- Invalid flag values → error message + exit code 1
- `gst_parse_launch()` failure → error message + exit code 1
- GStreamer bus errors → only printed for non-window-close errors + pipeline shutdown
