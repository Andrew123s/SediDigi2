# README capture.sh

## What the script does

1. Prompts the user for a recording name (e.g. "test01").
2. Creates a directory at `/home/dev/Videos/<name>` (for future frame extraction) and records a video to `/home/dev/Videos/<name>`.
3. Launches a `gst-launch-1.0` pipeline using the onboard CSI camera (via `nvarguscamerasrc`).

## GStreamer pipeline breakdown

The camera is configured with fixed settings:

- **Sensor mode 0** – highest sensor resolution
- **Gain** locked to 1 (no auto-gain)
- **ISP digital gain** locked to 1
- **Exposure time** fixed at 2.5 ms
- **White balance mode 4**, auto white balance locked
- **Auto exposure** locked
- **Temporal noise reduction** and **edge enhancement** are disabled
- **Saturation** at neutral (1.0)
- **Resolution** `4032 × 3040` at **21 fps** (means full sensor readout)

The video stream is split using a `tee` element:

### Branch A

Converts the raw NVMM frames (`nvvidconv`), encodes them as JPEG, muxes them into a video container, and writes to `/home/dev/Videos/<name>`.

### Branch B 

Downscales the stream to `1280 × 960`, applies EGL transform, and displays a live preview via `nveglglessink`.

## Summary

The script captures a high-resolution video (4032×3040, 21 fps) from the Jetson Orin Nano's CSI camera and saves it as a Motion JPEG video file. All camera parameters (gain, exposure, white balance) are locked to fixed values, making it behave like a manual camera. A downscaled live preview is shown on the display. Recording is stopped by pressing `Ctrl+C`.
