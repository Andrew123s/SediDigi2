from ultralytics import YOLO
import torch
import torchvision
import cv2

model = YOLO("model.engine")

cap = cv2.VideoCapture("input.mp4")
w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = cap.get(cv2.CAP_PROP_FPS)

out = cv2.VideoWriter("output.mp4", cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

while True:
    ret, frame = cap.read()
    if not ret:
        break

    results = model(frame, verbose=False)

    for r in results:
        boxes = r.boxes.xyxy
        confs = r.boxes.conf
        clss = r.boxes.cls

        if boxes.numel():
            idx = torchvision.ops.nms(boxes, confs, iou_thres=0.5)
            boxes = boxes[idx]
            confs = confs[idx]
            clss = clss[idx]

        for b, c, cls_id in zip(boxes, confs, clss):
            x1, y1, x2, y2 = map(int, b)
            label = f"{model.names[int(cls_id)]} {c:.2f}"
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, label, (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    out.write(frame)

cap.release()
out.release()
