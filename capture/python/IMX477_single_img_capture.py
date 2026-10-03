#!/usr/bin/env python3
"""
Single Image Capture

Hardware: Jetson Orin Nano Developer Kit with installed JetPack
Camera: ArduCam IMX477 on port CAM0, device available via /dev/video0

Captures a single frame via nvarguscamerasrc and saves it as JPEG.

Dependencies:
    sudo apt install python3-gi gir1.2-gstreamer-1.0 gir1.2-gst-plugins-base-1.0

Usage:
    python3 single_img_capture.py
    python3 single_img_capture.py output.jpg
    python3 single_img_capture.py output.jpg 1920 1080
"""

import sys
import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib

Gst.init(sys.argv)

# --- defaults ---
output_path = sys.argv[1] if len(sys.argv) > 1 else "capture.jpg"
width = int(sys.argv[2]) if len(sys.argv) > 2 else 3840
height = int(sys.argv[3]) if len(sys.argv) > 3 else 2160
sensor_id = 0
timeout_seconds = 10 # ...should be more than enough!

# build pipeline acc. to the scheme
#   nvarguscamerasrc -> NVMM raw (NV12) -> nvvidconv -> CPU raw (I420) -> jpegenc -> multifilesink
pipeline_desc = (
    f"nvarguscamerasrc sensor-id={sensor_id} ! "
    f"video/x-raw(memory:NVMM), width={width}, height={height}, format=NV12, framerate=30/1 ! "
    f"nvvidconv ! video/x-raw, format=I420 ! "
    f"jpegenc quality=95 ! "
    f"multifilesink location={output_path} max-files=1"
)

pipeline = Gst.parse_launch(pipeline_desc)

bus = pipeline.get_bus()
pipeline.set_state(Gst.State.PLAYING)
print(f"Capturing {width}x{height} from sensor {sensor_id}...")

msg = bus.timed_pop_filtered(
    Gst.SECOND * timeout_seconds,
    Gst.MessageType.EOS | Gst.MessageType.ERROR,
)

if msg is not None:
    if msg.type == Gst.MessageType.ERROR:
        err, debug = msg.parse_error()
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"Saved to {output_path}")
else:
    print(f"Timeout after {timeout_seconds}s", file=sys.stderr)

pipeline.set_state(Gst.State.NULL)

