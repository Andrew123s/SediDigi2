# SediDigi/inference

This folder contains real-time YOLOvx inference components designed to run on the Jetson Orin Nano with the ArduCam IMX477.

## Files

- `inference_arducam.py` — Real-time YOLOv8s (based on COCO dataset with 80 classes)inference using TensorRT. Captures from ArduCam IMX477 (via `nvarguscamerasrc`), runs detection on GPU (640x640), draws bounding boxes, writes an annotated MP4, and provides a live preview (OpenCV GUI or MJPEG stream).
- `yolov8s.engine` — TensorRT FP16 engine built from `yolov8s.onnx` (COCO 80 classes). Excluded from Git via `.gitignore`.
- `yolov8s.onnx` — ONNX model downloaded from ultralytics/assets (v8.4.0). Excluded from Git via `.gitignore`.
- `inference_example_01.py` — Minimal example showing YOLO (engine-based) inference on a pre-recorded video file with NMS and simple drawing (legacy/reference).
- `check_deepstream.sh` — Diagnostic script to check for DeepStream, TensorRT, GStreamer, CUDA, and Jetson L4T environment.

## TODO

- [ ] implementation of YOLOvx model inference in C++, with full GPU support, using a suitable framework
- [ ] inference performance test

## Notes (2026-09-23)

- Camera: full sensor resolution 4032x3040 is supported via `nvarguscamerasrc`. Reliable framerate is 15 fps (21 fps not stable). Default is 15 fps.
- No GPU-accelerated PyTorch available on this platform (PyTorch aarch64 wheels require `libcusparseLt.so.0`, not present; NVIDIA JetPack wheel index not reachable). Inference uses ONNX + TensorRT (`trtexec`) with pycuda for GPU I/O.
- Live preview: system OpenCV is headless, so an automatic MJPEG stream on port 8080 is provided when no GUI is available. With a local display and GUI-enabled OpenCV, the native window is used.
- Input preprocessing uses letterbox (640x640). Output video is written as MP4 (mp4v) at the selected capture resolution.