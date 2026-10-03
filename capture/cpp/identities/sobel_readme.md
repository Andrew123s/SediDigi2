# sobel.cpp – apply OpenCV Sobel via identity handoff

## Overview

Minimal demo of in‑place frame processing inside a GStreamer pipeline.
Uses the `identity` element's `handoff` signal to intercept each buffer,
apply `cv::Sobel` (chosen due its simplicity) on the Y plane of NV12, and pass it downstream.

The processing is a pure GStreamer plugin element callback within a single linear pipeline.

## Pipeline

```
nvarguscamerasrc
  → nvvidconv (NVMM → system memory)
  → video/x-raw, NV12, 4032×3040
  → identity name=proc
      ↓ [ handoff signal: cv::Sobel on Y plane ]
  → queue(max-size-buffers=5)
  → x264enc bitrate=80000 speed-preset=1
  → matroskamux
  → filesink (sobel.mkv)
```

## Dependencies

- GStreamer 1.20.3 (`gstreamer-1.0`, `gstreamer-app-1.0`, `gstreamer-video-1.0`)
- NVIDIA GStreamer plugins (JetPack / `nvidia-l4t-gstreamer`)
- OpenCV 4.8.0 (`imgproc`)
- CMake 3.22.1
- g++ 11.4.0

## Build

```bash
cmake -S . -B build
cmake --build build
```

## Usage

```bash
./build/sobel <recording-name>
       [--sensor-id <n>] [--framerate <num/den>]
       [--tnr-mode <0|1|2>] [--tnr-strength <f>]
       [--ee-mode <0|1|2>]
```

### Flags

| Flag | Default | Valid | Description |
|---|---|---|---|
| `<recording-name>` | – | any string | Directory under `/home/dev/Videos/` |
| `--sensor-id` | `0` | `>= 0` | Camera sensor ID |
| `--framerate` | `21/1` | `num/den` | Framerate override |
| `--tnr-mode` | `1` | `0,1,2` | Temporal Noise Reduction |
| `--tnr-strength` | `0.1` | `0.0–1.0` | Only when `--tnr-mode > 0` |
| `--ee-mode` | `0` | `0,1,2` | Edge Enhancement |

### Example

```bash
./build/sobel demo
ffplay /home/dev/Videos/demo/sobel.mkv
```

## Implementation Details

### identity handoff

- `identity name=proc` inserted between `nvvidconv` and `queue`
- Handoff connected via `g_signal_connect(proc, "handoff", …)`
- Property `signal-handoffs=TRUE` enables the signal
- Callback receives the raw `GstBuffer` – no sample handling needed
- Buffer is mapped `GST_MAP_READWRITE` and the Y plane is wrapped in
  `cv::Mat(CV_8UC1, height, width, data)` for `cv::Sobel` in place
- UV planes pass through unchanged

### Shutdown

Standard `gst_element_send_event(pipeline, EOS)` – EOS flows through the
single chain normally, no two‑chain complication.
