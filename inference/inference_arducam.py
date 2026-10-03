#!/usr/bin/env python3
"""
Real-time YOLOv8s (COCO) inference on the ArduCam IMX477 at full sensor
resolution (4032x3040), NVIDIA Jetson Orin Nano, TensorRT engine.

Usage:
    python3 inference_arducam.py                     # live preview + video
    python3 inference_arducam.py --no-show           # headless, video only
    python3 inference_arducam.py --frames 30         # stop after 30 frames

Dependencies (venv .venv): pycuda, tensorrt (system), opencv, numpy, python3-gi.
Engine yolov8s.engine must exist next to this script (built via trtexec).
"""

import argparse
import gc
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
import cv2
import pycuda.driver as cuda
import tensorrt as trt

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent / "capture" / "python"))
from imx477_capture import IMX477Capture

COCO_NAMES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
    "truck", "boat", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag",
    "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite",
    "baseball bat", "baseball glove", "skateboard", "surfboard",
    "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon",
    "bowl", "banana", "apple", "sandwich", "orange", "broccoli", "carrot",
    "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant",
    "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote",
    "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
]


def letterbox(img, size=640, color=(114, 114, 114)):
    h, w = img.shape[:2]
    s = size / max(h, w)
    nw, nh = int(round(w * s)), int(round(h * s))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((size, size, 3), color, dtype=np.uint8)
    dx, dy = (size - nw) // 2, (size - nh) // 2
    canvas[dy:dy + nh, dx:dx + nw] = resized
    return canvas, s, dx, dy


def preprocess(frame_bgr, size=640):
    canvas, s, dx, dy = letterbox(frame_bgr, size)
    blob = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    blob = np.transpose(blob, (2, 0, 1))[None]
    return np.ascontiguousarray(blob), s, dx, dy


def decode_output(raw, s, dx, dy, conf_th, iou_th):
    data = np.transpose(raw.reshape(-1, raw.shape[-1]))
    boxes_cxcywh = data[:, 0:4]
    scores = data[:, 4:]
    class_ids = np.argmax(scores, axis=1)
    confs = scores[np.arange(scores.shape[0]), class_ids]

    keep = np.where(confs >= conf_th)[0]
    if keep.size == 0:
        return [], [], []
    boxes_cxcywh = boxes_cxcywh[keep]
    confs = confs[keep]
    class_ids = class_ids[keep]

    x1 = (boxes_cxcywh[:, 0] - boxes_cxcywh[:, 2] / 2 - dx) / s
    y1 = (boxes_cxcywh[:, 1] - boxes_cxcywh[:, 3] / 2 - dy) / s
    x2 = (boxes_cxcywh[:, 0] + boxes_cxcywh[:, 2] / 2 - dx) / s
    y2 = (boxes_cxcywh[:, 1] + boxes_cxcywh[:, 3] / 2 - dy) / s
    w, h = x2 - x1, y2 - y1

    indices = cv2.dnn.NMSBoxes(
        list(zip(x1.tolist(), y1.tolist(), w.tolist(), h.tolist())),
        confs.tolist(), conf_th, iou_th)
    if len(indices) == 0:
        return [], [], []
    idx = np.asarray(indices).reshape(-1)
    return (np.stack([x1[idx], y1[idx], x2[idx], y2[idx]], axis=1).astype(int),
            confs[idx], class_ids[idx])


def gui_available():
    info = cv2.getBuildInformation()
    return any(tag in info for tag in ("GTK", "Qt", "Cocoa", "Emscripten"))


class MjpegStream:
    def __init__(self):
        self._frame = None
        self._lock = threading.Lock()
        self._server = None
        self._handler_made = False

    def publish(self, frame):
        ok, jpg = cv2.imencode(".jpg", frame,
                               [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ok:
            with self._lock:
                self._frame = jpg.tobytes()

    @property
    def handler(self):
        if self._handler_made:
            return self._handler
        stream = self

        class _H(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type",
                                 "multipart/x-mixed-replace; boundary=fr")
                self.end_headers()
                try:
                    while True:
                        with stream._lock:
                            data = stream._frame
                        if data:
                            try:
                                self.wfile.write(b"--fr\r\nContent-Type: "
                                                 b"image/jpeg\r\n\r\n")
                                self.wfile.write(data)
                                self.wfile.write(b"\r\n")
                                self.wfile.flush()
                            except (BrokenPipeError, ConnectionResetError):
                                return
                except Exception:
                    return

            def log_message(self, *a):
                pass

        self._handler = _H
        self._handler_made = True
        return self._handler

    def start(self, port=8080):
        self._server = ThreadingHTTPServer(("0.0.0.0", port), self.handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return port

    def stop(self):
        if self._server:
            self._server.shutdown()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.stop()
        return False


def main():
    ap = argparse.ArgumentParser(description="YOLOv8s ArduCam inference")
    ap.add_argument("--width", type=int, default=4032)
    ap.add_argument("--height", type=int, default=3040)
    ap.add_argument("--fps", type=int, default=15)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--iou", type=float, default=0.45)
    ap.add_argument("--out", type=str, default="output_arducam.mp4")
    ap.add_argument("--frames", type=int, default=0)
    ap.add_argument("--engine", type=str, default="yolov8s.engine")
    ap.add_argument("--no-show", action="store_true")
    ap.add_argument("--test-image", type=str, default="",
                    help="Detect on a still image instead of using the camera")
    args = ap.parse_args()

    cuda.init()
    ctx = cuda.Device(0).make_context()
    try:
        logger = trt.Logger(trt.Logger.WARNING)
        with open(SCRIPT_DIR / args.engine, "rb") as f:
            engine = trt.Runtime(logger).deserialize_cuda_engine(f.read())
        if engine is None:
            raise RuntimeError(f"Could not load engine: {args.engine}")

        inp_name = out_name = None
        for i in range(engine.num_io_tensors):
            name = engine.get_tensor_name(i)
            if engine.get_tensor_mode(name) == trt.TensorIOMode.INPUT:
                inp_name = name
            else:
                out_name = name
        assert inp_name and out_name

        inp_shape = engine.get_tensor_shape(inp_name)
        out_shape = engine.get_tensor_shape(out_name)

        h_in = cuda.pagelocked_empty(int(np.prod(inp_shape)), dtype=np.float32)
        h_out = cuda.pagelocked_empty(int(np.prod(out_shape)), dtype=np.float32)
        d_in = cuda.mem_alloc(h_in.nbytes)
        d_out = cuda.mem_alloc(h_out.nbytes)

        ctx_context = engine.create_execution_context()
        ctx_context.set_tensor_address(inp_name, int(d_in))
        ctx_context.set_tensor_address(out_name, int(d_out))

        gui = gui_available()
        use_gui = not args.no_show and bool(os.environ.get("DISPLAY")) and gui
        if not args.no_show and not use_gui:
            stream = MjpegStream()
            port = stream.start()
            print(f"Live preview: http://<this-host>:{port}/  "
                  f"(no OpenCV GUI available: gui={gui}, "
                  f"DISPLAY={bool(os.environ.get('DISPLAY'))})", flush=True)
        else:
            stream = None

        def infer(frame):
            blob, s, dx, dy = preprocess(frame, args.imgsz)
            h_in[:] = blob.reshape(-1)
            cuda.memcpy_htod(d_in, h_in)
            ctx_context.execute_v2([int(d_in), int(d_out)])
            cuda.memcpy_dtoh(h_out, d_out)
            return decode_output(
                h_out[:int(np.prod(out_shape))].reshape(out_shape),
                s, dx, dy, args.conf, args.iou)

        def draw(frame, boxes, confs, cls):
            for (x1, y1, x2, y2), c, ci in zip(boxes, confs, cls):
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
                label = f"{COCO_NAMES[ci]} {c:.2f}"
                cv2.putText(frame, label, (x1, max(y1 - 6, 0)),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

        if args.test_image:
            frame = cv2.imread(args.test_image)
            if frame is None:
                raise RuntimeError(f"Could not read image: {args.test_image}")
            boxes, confs, cls = infer(frame)
            print(f"{args.test_image}: {len(boxes)} object(s)", flush=True)
            draw(frame, boxes, confs, cls)
            out_path = args.out
            if out_path.endswith((".mp4", ".avi", ".mkv")):
                out_path = str(SCRIPT_DIR / ("annotated_" +
                                             Path(args.test_image).name))
            cv2.imwrite(out_path, frame)
            print(f"Annotated to: {out_path}", flush=True)
            if stream:
                stream.publish(cv2.resize(frame, (1920, 1448)))
                time.sleep(2)
            return

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(args.out, fourcc, args.fps,
                              (args.width, args.height))
        if not out.isOpened():
            raise RuntimeError(f"Could not open VideoWriter: {args.out}")

        print(f"Starting: {args.width}x{args.height}@{args.fps} fps, "
              f"imgsz={args.imgsz}, conf={args.conf}, iou={args.iou}")
        with IMX477Capture(width=args.width, height=args.height,
                           framerate=args.fps) as cam:
            frame_no = 0
            while args.frames == 0 or frame_no < args.frames:
                frame = None
                for _ in range(10):
                    try:
                        frame = cam.capture()
                        break
                    except TimeoutError:
                        pass
                if frame is None:
                    raise RuntimeError("No camera frame available (framerate "
                                       "possibly unsupported)")
                boxes, confs, cls = infer(frame)
                draw(frame, boxes, confs, cls)

                out.write(frame)
                frame_no += 1
                print(f"[{frame_no}] {len(boxes)} object(s)", flush=True)

                if stream:
                    stream.publish(cv2.resize(frame, (1920, 1448)))
                elif use_gui:
                    cv2.imshow("Inference", cv2.resize(frame, (1920, 1448)))
                    c = cv2.waitKey(1) & 0xFF
                    if c in (ord("q"), 27):
                        break

        out.release()
        if use_gui:
            cv2.destroyAllWindows()
        if stream:
            stream.stop()
    finally:
        try:
            d_in.free()
            d_out.free()
        except Exception:
            pass
        ctx_context = None
        engine = None
        gc.collect()
        try:
            cuda.Context.pop()
        except Exception:
            pass


if __name__ == "__main__":
    main()