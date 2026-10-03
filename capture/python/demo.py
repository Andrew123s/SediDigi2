#!/usr/bin/env python3
"""
Live preview demo (continuous image aquisition) for IMX477Capture library module.

Usage:
    python3 demo.py
    python3 demo.py 1920 1080
"""

import sys
import signal
import cv2
from imx477_capture import IMX477Capture

running = True

def handle_signal(sig, frame):
    global running
    running = False

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

width = int(sys.argv[1]) if len(sys.argv) > 1 else 3840
height = int(sys.argv[2]) if len(sys.argv) > 2 else 2160

print(f"Starting live preview {width}x{height} (press 'q' or Ctrl+C to quit)...")

with IMX477Capture(width=width, height=height, framerate=30) as cam:
    while running:
        try:
            frame = cam.capture()
            ##frame = frame[:, :, ::-1]
            cv2.imshow("IMX477 Live", frame)
        except TimeoutError:
            continue

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()
    cv2.waitKey(1)
    print("Preview stopped.")
