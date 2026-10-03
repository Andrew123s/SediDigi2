# README denoise_capture.sh

## What the script does

1. Prompts the user for a recording name (e.g. "test01").
2. Creates a directory at `/home/dev/Videos/<name>` and records two H.264 MP4 files inside: `fullres.mp4` and `downsampled.mp4`.
3. Launches a `gst-launch-1.0` pipeline using the onboard CSI camera (via `nvarguscamerasrc`).

## GStreamer pipeline breakdown

The camera is configured with fixed settings:

- **Sensor mode 0** – highest sensor resolution
- **Gain** locked to 1 (no auto-gain)
- **ISP digital gain** locked to 1
- **Exposure time** fixed at 2.5 ms
- **White balance mode 4**, auto white balance locked
- **Auto exposure** locked
- **Temporal noise reduction (TNR)** enabled at mode 1, strength 0.1
- **Edge enhancement** disabled
- **Saturation** at neutral (1.0)
- **Resolution** `4032 × 3040` (no explicit framerate constraint, sensor default)

The video stream is split into three branches using a `tee` element:

### Branch A – Live preview
Downscales the stream to `1280 × 960`, applies EGL transform, and displays a live preview via `nveglglessink`. Uses a small queue (`max-size-buffers=1`, `leaky=downstream`) so the preview never blocks the recording branches.

### Branch B – Full resolution recording
Encodes the raw NVMM frames directly with hardware H.264 (`nvv4l2h264enc`, 80 Mbps), parses with `h264parse`, muxes into MP4 (`qtmux`), and writes to `fullres.mp4`. The queue buffers up to 50 frames without dropping (`leaky=0`) to absorb encoding latency.

### Branch C – Downsampled recording
Converts the stream to `1008 × 760` via `nvvidconv`, encodes with hardware H.264 at 20 Mbps, parses with `h264parse`, muxes into MP4 (`qtmux`), and writes to `downsampled.mp4`. The queue buffers up to 30 frames without dropping.

## Summary

The script captures a high-resolution video (4032×3040) from the Jetson Orin Nano's CSI camera with temporal noise reduction enabled and saves it as two H.264 MP4 files – a full-resolution copy at high bitrate (80 Mbps) and a downsampled lower-bitrate copy (1008×760, 20 Mbps). All camera parameters (gain, exposure, white balance) are locked to fixed values. A downscaled live preview is shown on the display. Recording is stopped by pressing `Ctrl+C`.
