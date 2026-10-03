"""
IMX477 Camera Capture Library

Hardware: Jetson Orin Nano Developer Kit with installed JetPack
Camera: ArduCam IMX477 on port CAM0, device available via /dev/video0

Captures frames via nvarguscamerasrc and returns them as
numpy arrays (BGR) ready for OpenCV processing.

Dependencies:
    sudo apt install python3-gi gir1.2-gstreamer-1.0 gir1.2-gst-plugins-base-1.0 gir1.2-gst-app-1.0
    pip3 install opencv-python numpy

Usage:
    # direct usage
    cam = IMX477Capture(width=1920, height=1080)
    frame = cam.capture()

    # as context manager
    with IMX477Capture(framerate=60) as cam:
        frame = cam.capture()
"""

import time
import numpy as np
import gi

gi.require_version("Gst", "1.0")
gi.require_version("GstApp", "1.0")
from gi.repository import Gst, GstApp

Gst.init(None)


class IMX477Capture:
    def __init__(self, sensor_id=0, width=3840, height=2160, framerate=30, timeout=10):
        self.sensor_id = sensor_id
        self.width = width
        self.height = height
        self.framerate = framerate
        self.timeout = timeout

        pipeline_desc = (
            f"nvarguscamerasrc sensor-id={sensor_id} ! "
            f"video/x-raw(memory:NVMM), width={width}, height={height}, format=NV12, framerate={framerate}/1 ! "
            f"nvvidconv ! video/x-raw, format=BGRx ! "
            f"appsink name=sink emit-signals=False sync=False max-buffers=1 drop=True"
        )

        self.pipeline = Gst.parse_launch(pipeline_desc)
        self.sink = self.pipeline.get_by_name("sink")
        self.pipeline.set_state(Gst.State.PLAYING)

    def capture(self):
        sample = self.sink.try_pull_sample(Gst.SECOND)
        if sample is None:
            raise TimeoutError("No frame received")

        buffer = sample.get_buffer()
        success, map_info = buffer.map(Gst.MapFlags.READ)
        if not success:
            raise RuntimeError("Failed to map buffer")

        try:
            frame = np.frombuffer(map_info.data, dtype=np.uint8).reshape(self.height, self.width, 4)
            frame = frame[:, :, :3]
            return frame
        finally:
            buffer.unmap(map_info)

    def close(self):
        self.pipeline.set_state(Gst.State.NULL)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
