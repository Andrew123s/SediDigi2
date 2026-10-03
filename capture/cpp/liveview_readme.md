# liveview.cpp – Live Preview Only

## Overview

Pure live preview tool based on `capture2.cpp` but without any file output.
Displays the camera feed in a window and exits on ENTER, Ctrl+C, or window close.

Key differences to `capture2.cpp`:

| | capture2.cpp | liveview.cpp |
|---|---|---|
| **Tee branches** | 3 (A preview + B fullres + C downsampled) | 1 (preview only) |
| **File output** | fullres.mp4 + downsampled.mp4 | none |
| **Recording name** | required | not needed |
| **Extra CLI flags** | – | `--width`, `--exposuretime` |

## Dependencies

- GStreamer 1.20.3 (`gstreamer-1.0`, `gstreamer-app-1.0`, `gstreamer-video-1.0`)
- NVIDIA GStreamer plugins (JetPack / `nvidia-l4t-gstreamer`)
- CMake 3.22.1
- g++ 11.4.0

All libraries are preinstalled on the system, no additional installation was required.

## Files

| File | Description |
|---|---|
| `liveview.cpp` | Main source file |
| `CMakeLists.txt` | CMake build configuration (Target `liveview`) |

## Build

```bash
mkdir -p build
cmake -S . -B build
cmake --build build
```

## Usage

```bash
./build/liveview [--sensor-id <n>] [--framerate <num/den>]
                 [--tnr-mode <0|1|2>] [--tnr-strength <f>]
                 [--ee-mode <0|1|2>] [--exposuretime <ns>]
                 [--width <n>]
```

| Flag | Default | Valid values | Description |
|---|---|---|---|
| `--sensor-id` | `0` | `>= 0` | Camera sensor ID |
| `--framerate` | `21/1` | `num/den` with `num>0, den>0` | Override the default 21/1 framerate |
| `--tnr-mode` | `1` | `0, 1, 2` | Temporal Noise Reduction |
| `--tnr-strength` | `0.1` | `0.0 – 1.0` | Only valid when `--tnr-mode > 0` |
| `--ee-mode` | `0` | `0, 1, 2` | Edge Enhancement |
| `--exposuretime` | `2500000` ns | `> 0` | Exposure time in ns |
| `--width` | `1280` | `> 0, % 4 == 0` | Preview width; height = width × ¾ |

Examples:

```bash
./build/liveview
./build/liveview --width 1920
./build/liveview --tnr-mode 2 --tnr-strength 0.5 --framerate 30/1
./build/liveview --exposuretime 47000000
```

Optional flags can appear in any order.

## Implementation Details

### Command-line arguments

A `Config` struct holds all parsed values; defaults are defined as a static const instance. Arguments are parsed in a loop over `argv[1..]` via `strcmp()` – order is arbitrary. 

After parsing, a post-validation step rejects `--tnr-strength` when `tnr-mode == 0`. The `--width` flag requires `> 0 && % 4 == 0` to ensure proper alignment for the video scaler. `--exposuretime` accepts a value in nanoseconds for the `exposuretimerange` property (no value range considered).

### GStreamer Pipeline

The pipeline is built with a single `g_strdup_printf` call (no GString needed – only the optional framerate and tnr-strength parts use conditional substrings).

```
nvarguscamerasrc
  (sensor-id=<n>, tnr-mode=<n>[, tnr-strength=<f>], ee-mode=<n>,
   gainrange="1 1", ispdigitalgainrange="1 1",
   exposuretimerange="<ns> <ns>", wbmode=4,
   awblock=true, aelock=true, saturation=1)
  → caps: video/x-raw(memory:NVMM), width=4032, height=3040[, framerate=<num>/<den>]
  → nvvidconv
  → caps: video/x-raw(memory:NVMM), width=<n>, height=<n×¾>
  → nvegltransform → nveglglessink sync=false
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

### Error Handling

The error handling is minimal:

- Invalid flag values → error message + exit code 1
- `gst_parse_launch()` failure → error message + exit code 1
- GStreamer bus errors → only printed for non-window-close errors + pipeline shutdown
