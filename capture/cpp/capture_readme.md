# capture.cpp – C++ Implementation of capture.sh

## Overview

This is an advanced C++ reimplementation of the `capture.sh` script as a command-line tool. It records a high-resolution video (default: 4032×3040 @ 21 fps) from the Jetson Orin Nano's CSI camera using the GStreamer API, saves it as Motion JPEG, and shows a live preview on the display.

## Dependencies

- GStreamer 1.20.3 (`gstreamer-1.0`, `gstreamer-app-1.0`, `gstreamer-video-1.0`)
- NVIDIA GStreamer plugins (these are part of the JetPack / `nvidia-l4t-gstreamer`)
- CMake 3.22.1
- g++ 11.4.0

All libraries are preinstalled on the system, no additional installation was required.

## Files

| File | Description |
|---|---|
| `capture.cpp` | Main source file |
| `CMakeLists.txt` | CMake build configuration |

## Build

```bash
mkdir -p build
cmake -S . -B build
cmake --build build
```

The binary is placed in the folder `build/capture`.

## Usage

```bash
./build/capture <recording-name> [--sensor-id <n>] [--framerate <n/n>]
```

Examples:

```bash
./build/capture test01
./build/capture --sensor-id 1 test01
./build/capture --framerate 30/1 test01
./build/capture --sensor-id 1 --framerate 30/1 test01
```

Optional flags can appear in any order before or after the recording name.

Remark: No matter which port the camera is connected to, it can always be accessed under sensor ID 0.
This makes the flag `--sensor-id` unnecessary, at least for the current configuration.

### Defaults

| Parameter | Default |
|---|---|
| `--sensor-id` | `0` (cam0) |
| `--framerate` | `21/1` |

This will:

1. Create the directory `/home/dev/Videos/test01/` for later still images
2. Record the video to `/home/dev/Videos/<name>`
3. Show a live preview window (1280×960)
4. Stop when ENTER is pressed in the terminal or when the preview window is closed

## Implementation Details

### Command-line arguments

The recording name is a mandatory positional argument.
Optional flags (`--sensor-id`, `--framerate`) are parsed in a loop over `argv` via `strcmp()` and can appear in any order.
A `Config` struct holds all parsed values; defaults are defined as a static const instance.

### GStreamer Pipeline

The pipeline is built via `gst_parse_launch()` using a pipeline string derived from the original `gst-launch-1.0` command (with `sensor-id` and `framerate` as configurable parameters):

```
nvarguscamerasrc
  (sensor-id=<n>, sensor-mode=0, gainrange="1 1", ispdigitalgainrange="1 1",
   exposuretimerange="2500000 2500000", wbmode=4,
   awblock=true, aelock=true, tnr-mode=0, ee-mode=0, saturation=1)
  → caps: video/x-raw(memory:NVMM), width=4032, height=3040, framerate=<num>/<den>
  → tee
     ├→ queue → nvvidconv → jpegenc → avimux → filesink (recording)
     └→ queue (max-size-buffers=1, leaky=downstream)
        → nvvidconv → caps: video/x-raw(NVMM), width=1280, height=960
        → nvegltransform → nveglglessink (preview)
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

The frame directory `/home/dev/Videos/<name>/` is created at startup via `mkdir()` with `0755` permissions, matching the original script's `mkdir -p` behavior.

### Error Handling

The error handling is quite minimal:

- Missing argument → usage message + exit code 1
- `gst_parse_launch()` failure → error message + exit code 1
- GStreamer bus errors → only printed for non-window-close errors + pipeline shutdown
