#!/usr/bin/env python3
"""
OpenCV Frame Capture from ArduCam IMX477

Hardware: Jetson Orin Nano Developer Kit with installed JetPack
Camera: ArduCam IMX477 on port CAM0, device available via /dev/video0

Captures a single frame via nvarguscamerasrc and returns it as a
numpy array (BGR) ready for OpenCV processing.

Dependencies:
    sudo apt install python3-gi gir1.2-gstreamer-1.0 gir1.2-gst-plugins-base-1.0 gir1.2-gst-app-1.0
    pip3 install opencv-python numpy

Usage:
    python3 IMX477_opencv_capture.py
    python3 IMX477_opencv_capture.py 1920 1080
"""

import sys
import numpy as np
import cv2
import gi

gi.require_version("Gst", "1.0")
gi.require_version("GstApp", "1.0")
from gi.repository import Gst, GstApp

Gst.init(sys.argv)

# --- defaults ---
width = int(sys.argv[1]) if len(sys.argv) > 1 else 3840
height = int(sys.argv[2]) if len(sys.argv) > 2 else 2160
sensor_id = 0
timeout_seconds = 10

# pipeline: nvarguscamerasrc -> NV12 (NVMM) -> nvvidconv -> BGRx (CPU) -> appsink
pipeline_desc = (
    f"nvarguscamerasrc sensor-id={sensor_id} ! "
    f"video/x-raw(memory:NVMM), width={width}, height={height}, format=NV12, framerate=30/1 ! "
    f"nvvidconv ! video/x-raw, format=BGRx ! "
    f"appsink name=sink emit-signals=False sync=False max-buffers=1 drop=True"
)

pipeline = Gst.parse_launch(pipeline_desc)
sink = pipeline.get_by_name("sink")

try:
    bus = pipeline.get_bus()
    pipeline.set_state(Gst.State.PLAYING)
    print(f"Capturing {width}x{height} from sensor {sensor_id}...")

    msg = bus.timed_pop_filtered(
        Gst.SECOND * timeout_seconds,
        Gst.MessageType.EOS | Gst.MessageType.ERROR,
    )

    if msg is not None and msg.type == Gst.MessageType.ERROR:
        err, debug = msg.parse_error()
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)

    sample = sink.try_pull_sample(Gst.SECOND)

    if sample is None:
        print(f"No frame received (timeout {timeout_seconds}s)", file=sys.stderr)
        sys.exit(1)

    buffer = sample.get_buffer()
    success, map_info = buffer.map(Gst.MapFlags.READ)

    if not success:
        print("Failed to map buffer", file=sys.stderr)
        sys.exit(1)

    frame = np.frombuffer(map_info.data, dtype=np.uint8).reshape(height, width, 4)
    frame = frame[:, :, :3]

    buffer.unmap(map_info)
    print(f"Frame shape: {frame.shape}, dtype: {frame.dtype}")
    cv2.imshow("Captured Frame", frame)
    print("Press any key in the window to exit...")
    
    cv2.waitKey(0)
    cv2.destroyAllWindows()
finally:
    pipeline.set_state(Gst.State.NULL)
