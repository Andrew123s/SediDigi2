#!/usr/bin/env python

"""
The script implements a video-based object extraction and tracking pipeline designed for organisms moving over a uniform, stationary background (e.g., mites or insects). Its goal is to detect each individual, track it across frames, and save a representative set of cropped images for each tracked specimen.

Quick and dirty. Next step would be to GPU-accelerate this if keeping with the 30 fps
"""

import argparse
from pathlib import Path

#----------------------
from sort.sort import *

#----------------------
import av
import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor


def open_video(path):
    try_hwaccel = [
        # Nvidia
        {"hwaccel": "cuda", "hwaccel_output_format": "cuda"},
        {"hwaccel": "cuvid"},
        # Intel
        {"hwaccel": "qsv"},
        # AMD / Intel
        {"hwaccel": "vaapi", "hwaccel_device": "/dev/dri/renderD128"}
    ]

    # Try hardware accelerations in order
    for opts in try_hwaccel:
        try:
            return av.open(path, mode="r", options=opts)
        except av.error.FFmpegError:  # av.AVError no longer exists in PyAV >= 14
            continue

    # Fallback: software decode (always works)
    return av.open(path)


def match_tracks_to_detections(tracks, detections, min_iou=0.3):
    """
    Pair SORT output rows with the detections of the current frame.

    Returns (track_index, detection_index) pairs, matched one-to-one by
    maximum IoU. Pairs below min_iou are dropped.
    """
    if len(tracks) == 0 or len(detections) == 0:
        return []

    t = np.asarray(tracks[:, :4], dtype=float)[:, None, :]
    d = np.asarray(detections[:, :4], dtype=float)[None, :, :]
    iw = np.clip(np.minimum(t[..., 2], d[..., 2]) - np.maximum(t[..., 0], d[..., 0]), 0, None)
    ih = np.clip(np.minimum(t[..., 3], d[..., 3]) - np.maximum(t[..., 1], d[..., 1]), 0, None)
    inter = iw * ih
    area_t = (t[..., 2] - t[..., 0]) * (t[..., 3] - t[..., 1])
    area_d = (d[..., 2] - d[..., 0]) * (d[..., 3] - d[..., 1])
    iou = inter / (area_t + area_d - inter + 1e-9)

    rows, cols = linear_sum_assignment(-iou)
    return [(r, c) for r, c in zip(rows, cols) if iou[r, c] >= min_iou]


def split_component(comp, core_frac):
    """
    Split a binary component (uint8, 0/1) that contains several touching objects.

    Object cores are the parts of the component whose distance to the background is
    at least core_frac of the maximum distance. Each pixel is assigned to its nearest
    core. Returns one binary mask per object (a single mask if there is one core).
    """
    dist = cv2.distanceTransform(comp, cv2.DIST_L2, 5)
    cores = (dist >= core_frac * dist.max()).astype(np.uint8)
    n_cores, _ = cv2.connectedComponents(cores)
    if n_cores <= 2:   # background + one core
        return [comp]

    # Nearest-core assignment: every pixel gets the label of the closest core
    _, nearest = cv2.distanceTransformWithLabels(1 - cores, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_CCOMP)
    parts = [((nearest == lab) & (comp > 0)).astype(np.uint8) for lab in np.unique(nearest[cores > 0])]
    parts = [p for p in parts if p.any()]

    # Touching objects give parts of similar size; a narrow waist inside one object
    # (e.g. the head of a springtail) gives one small part. Only split in the first case.
    total = comp.sum()
    if min(p.sum() for p in parts) < 0.25 * total:
        return [comp]
    return parts


def select_samples(entries, n, mode):
    """
    Pick the crops to save for one track (entries are in frame order).

    'even' keeps every k-th detection (previous behaviour). 'best' first drops
    detections whose area differs strongly from the track's median area (merged
    with another object, or only partly detected), then splits the remaining
    detections into n consecutive segments and keeps the sharpest one of each.
    """
    if mode == 'even':
        step = max(len(entries) // n, 1)
        return entries[::step]

    if len(entries) <= n:
        return entries

    med = np.median([e['area'] for e in entries])
    pool = [e for e in entries if 0.7 * med <= e['area'] <= 1.3 * med]
    if len(pool) < n:   # not enough typical detections: take the n closest to the median size
        closest = sorted(range(len(entries)), key=lambda j: abs(entries[j]['area'] - med))[:n]
        pool = [entries[j] for j in sorted(closest)]

    return [max((pool[j] for j in seg), key=lambda e: e['sharpness'])
            for seg in np.array_split(np.arange(len(pool)), n) if len(seg)]


def extract_obj(args):
    """
    Process a video and extract moving objects from a static background.

    Per frame: LAB background subtraction produces a foreground mask, connected
    components become detections, and SORT runs online multi-object tracking.
    Crops (original, masked, background-filled) of each tracked object are kept
    in memory and written to <out>/base, <out>/pmask, <out>/cpmask once the
    video ends. With --drawing, an annotated video is produced as well.
    """

    video_path = Path(args.input)

    min_area = args.min_area   # minimum object area (in pixels)
    max_h = args.max_h         # maximum object height (in pixels)
    max_w = args.max_w         # maximum object width (in pixels)
    resize_factor =  args.resize
    n = args.num_samples
    d = args.delta

    # --- Make crops output directory
    out = video_path.with_suffix('')
    Path(out).mkdir(parents=True, exist_ok=True)
    Path(f"{out}/base").mkdir(parents=True, exist_ok=True)
    Path(f"{out}/pmask").mkdir(parents=True, exist_ok=True)
    Path(f"{out}/cpmask").mkdir(parents=True, exist_ok=True)

    # --- Setup capture (AV) ---
    container = open_video(video_path)
    stream = container.streams.video[0]
    stream.thread_type = "AUTO"  # multi-threaded decoding (frame + slice), ~2.7x faster on 4K HEVC
    fps = int(float(stream.average_rate))  # average_rate is an AVRational in PyAV >= 14

    if args.low_fps:
        fps = int(fps/2)

    twidth = stream.codec_context.width
    theight = stream.codec_context.height
    n_frames = stream.frames

    width  = int(twidth * resize_factor)
    height = int(theight * resize_factor)


    # --- Video writer setup ---
    if args.drawing:
        print(f"opening {out}__annot.mp4")
        out_cont = av.open(f"{out}__annot.mp4", mode="w")
        o_stream = out_cont.add_stream("h264", rate=fps)
        o_stream.width = width
        o_stream.height = height
        o_stream.pix_fmt = "yuv420p"


    color = [0, 215, 255] # Color for drawing annotations

    print(f'Running mask detection based on invert background color selection (bg model: {args.bg_model})')

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (args.close, args.close)) if args.close > 1 else None
    n_split = 0   # number of components split into several objects (--split)

    mot_tracker = Sort()
    tracked_objects = dict()

    # Background model selection (median | frame | temporal)
    bg_model = args.bg_model
    delta = int(255 * d / 100)   # cv2 LAB range, per-channel tolerance
    bg_ready = False
    bg_img = None                # per-pixel background reference (frame/temporal)
    bg_stack = []                # collected frames for 'temporal' model

    color_mask = np.zeros((int(height), int(width), 3), np.uint8) # Allocating drawing layer
    mask = np.zeros((int(theight), int(twidth)), np.uint8) # Allocating mask layer

    frame_id = 0

    for i, frame in enumerate(tqdm(container.decode(video=0), total=n_frames, desc="Processing frames")):

        if args.low_fps and i % 2 == 1:   # skip odd frames
            continue

        img = frame.to_ndarray(format="bgr24")

        lab_img = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)

        if  args.clahe:

            # Split channels
            l, a, b = cv2.split(lab_img)
            # Apply CLAHE on L channel only
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            cl = clahe.apply(l)
            # FIX: was LAB2BGR previously, leaving inRange on BGR with LAB thresholds.
            # Keep everything in LAB.
            lab_img = cv2.merge((cl, a, b))


        # --- Background model construction and masking ---
        if bg_model == 'median':
            # Getting the median color of the first frame, defined as the central background color.
            # This computation is slow (~100ms), hence is done only on the first frame.
            # This means that the background color must remain stable during the video capture.
            if not bg_ready:
                median_lab_color = np.median(lab_img, axis=[0,1])
                low_color = median_lab_color - delta
                high_color = median_lab_color + delta
                bg_ready = True

            mask[:] = cv2.inRange(lab_img, low_color, high_color)

        else:
            # Per-pixel background reference (bg_img) built with frame or temporal model.
            if bg_model == 'frame':
                # First frame as background image. Requires an object-free first frame.
                if not bg_ready:
                    bg_img = lab_img.copy()
                    bg_ready = True

            else:  # temporal
                # Per-pixel median over the first N frames. Robust to noise and transient
                # objects. NOTE: keeps N full frames in memory until collected.
                if not bg_ready:
                    bg_stack.append(lab_img.copy())
                    if len(bg_stack) == args.bg_frames:
                        bg_img = np.median(np.stack(bg_stack), axis=0).astype(np.uint8)
                        bg_stack = None
                        bg_ready = True
                    continue

            if bg_ready:
                diff = cv2.absdiff(lab_img, bg_img)
                # NOTE: use per-channel bounds: cv2.inRange(diff, 0, delta) with
                # scalar ints converts to Scalar(25,0,0,0) -> a/b tolerance clamped
                # to 0, turning almost the whole frame into foreground.
                mask[:] = cv2.inRange(diff, np.array([0, 0, 0]), np.array([delta, delta, delta]))

        frame_id += 1

        fgmask = cv2.bitwise_not(mask)

        # Recovering lost parts (appendages) - but unfortunately may also fuse close objects.
        # Kernel size set with --close (default 5, 0 = off).
        if kernel is not None:
            fgmask = cv2.dilate(fgmask, kernel, iterations=1)
            fgmask = cv2.erode(fgmask, kernel, iterations=1)

        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(fgmask) # Get instances from fgmask

        detections = list()  # to keep list of bbox
        crops = list()       # to keep object crops (img)
        masks = list()       # to keep object crops (masks)
        names = list()       # to keep object coord (frame n + loc)
        obj_id = list()      # to keep object_id (tracking)
        masked_crop = list() # to keep object crops (img with masked background)
        mask_objs = list()   # to keep the resized full img object masks if drawing
        areas = list()       # to keep object areas (crop selection)
        sharpness = list()   # to keep object sharpness (crop selection)

        def passes_filters(x, y, w, h, area):
            # Filter on min size, max height/width, elongation, and remove if close to top and bottom edge.
            aspect = max(w, h) / max(min(w, h), 1)
            return (area > min_area) and (h < max_h) and (w < max_w) and (y > 20) and ((y+h) < (theight-20)) \
                and (args.max_aspect <= 0 or aspect <= args.max_aspect)

        # Loop into the found segments.
        for obj in range(1, num_labels):

            x, y, w, h, area = stats[obj]
            if not passes_filters(x, y, w, h, area):
                continue

            comp = (labels[y:y+h, x:x+w] == obj).astype(np.uint8)
            parts = split_component(comp, args.split_core) if args.split else [comp]
            n_split += len(parts) > 1

            for part in parts:
                px, py, w, h = cv2.boundingRect(part)
                x0, y0 = x + px, y + py
                part_area = cv2.countNonZero(part)
                if len(parts) > 1 and not passes_filters(x0, y0, w, h, part_area):
                    continue

                detections.append([x0, y0, x0+w, y0+h, None])        # saving the detection bbox for tracking
                names.append(f"f{frame_id:05d}__x{x0}__y{y0}")       # naming the object by frame and location
                areas.append(part_area)

                # Crop box, optionally enlarged by a margin (--pad) and clipped to the frame
                pad = round(args.pad * max(w, h))
                cx0, cy0 = max(x0 - pad, 0), max(y0 - pad, 0)
                cx1, cy1 = min(x0 + w + pad, twidth), min(y0 + h + pad, theight)
                mask_crop = np.zeros((cy1 - cy0, cx1 - cx0), np.uint8)
                mask_crop[y0-cy0:y0-cy0+h, x0-cx0:x0-cx0+w] = part[py:py+h, px:px+w] * 255

                # Collecting the object crops and mask crops, kept in memory until the end
                # of the video. Tracking runs online per frame; a representative subset
                # (up to `n` samples) per tracked object is written once the video ends.

                img_crop = img[cy0:cy1, cx0:cx1]
                masks.append(mask_crop)
                crops.append(img_crop.copy())

                # Sharpness of the object pixels (variance of the Laplacian)
                lap = cv2.Laplacian(cv2.cvtColor(img_crop, cv2.COLOR_BGR2GRAY), cv2.CV_64F)
                sharpness.append(float(lap[mask_crop > 0].var()))

                # Masking the background of the object crop
                bgc = np.array([210, 100, 150], dtype=np.uint8)
                mcrops = img_crop.copy()
                mcrops[mask_crop == 0] = bgc
                masked_crop.append(mcrops)

                if args.drawing:
                    mask_obj = np.zeros((theight, twidth), np.uint8)   # frame-wide mask of the object
                    mask_obj[y0:y0+h, x0:x0+w] = part[py:py+h, px:px+w] * 255
                    mask_objs.append(
                        cv2.resize(mask_obj, (width, height), interpolation=cv2.INTER_AREA)
                        )

        if args.drawing:
            color_mask[:] = 0 # Reset the mask drawing layer
            # Make drawing layer (= copy of scaled down image)
            img_d = cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA)

            # Drawing
            for i in range(len(detections)):
                # Draw scaled bbox and cosmetic label
                rdet = [round(e * resize_factor) for e in detections[i][:4]]
                cv2.rectangle(img_d, (rdet[0],rdet[1]), (rdet[2],rdet[3]), color, round(5*resize_factor))
                cv2.putText(img_d, args.label, (rdet[0], rdet[1]-5), cv2.FONT_HERSHEY_SIMPLEX, 2*resize_factor, color, int(6*resize_factor))

                # Make border of the mask and draw on the mask layer
                dilated = cv2.dilate(mask_objs[i], None, iterations=1)
                eroded  = cv2.erode(mask_objs[i], None, iterations=1)
                border = dilated - mask_objs[i]
                color_mask[border > 0] = color

        # Tracking objects
        if len(detections) == 0:
            track_bbs_ids = mot_tracker.update(np.empty((0, 5)))
        else:
            detections = np.array(detections)
            track_bbs_ids = mot_tracker.update(detections)
            # SORT does not return tracks in detection order (and may return fewer),
            # so map each track back to the detection it was built from.
            for t, i in match_tracks_to_detections(track_bbs_ids, detections):
                detect = track_bbs_ids[t]
                obj_id = int(detect[4])
                tracked_objects.setdefault(obj_id, []).append(
                    {'crop': crops[i], 'mask': masks[i], 'masked_crop': masked_crop[i], 'name': names[i],
                     'area': areas[i], 'sharpness': sharpness[i]})

                # Drawing the tracked object id
                if args.drawing:
                    cv2.putText(img_d, f"{int(detect[4])}",
                                (int(detect[2] * resize_factor), int(detect[3] * resize_factor)+5),
                                cv2.FONT_HERSHEY_SIMPLEX, 2*resize_factor, color, int(6*resize_factor))

        if args.drawing:

            mask_binary = np.any(color_mask != 0, axis=2)
            img_d[mask_binary] = (
                        color_mask[mask_binary]
                        ).astype(np.uint8)


            av_frame = av.VideoFrame.from_ndarray(img_d, format="bgr24")
            packet = o_stream.encode(av_frame)
            if packet:
                out_cont.mux(packet)

    container.close()
    if args.drawing:
        out_cont.mux(o_stream.encode())  # flush frames still buffered in the encoder
        out_cont.close()

    if args.split:
        print(f"Split {n_split} components into several objects")
    print("Writing crop")

    # Parallelizing crop writing
    writer_pool = ThreadPoolExecutor(max_workers=args.threads)

    def write_img(path, img):
        cv2.imwrite(path, img)

    for obj_id in tracked_objects:
        # A representative subset of crops is saved per tracked object (see --select).
        for obj in select_samples(tracked_objects[obj_id], n, args.select):
            base = f"{out}/base/{Path(out).stem}__obj{obj_id}__{obj['name']}"
            pmask = f"{out}/pmask/{Path(out).stem}__obj{obj_id}__{obj['name']}"
            cpmask = f"{out}/cpmask/{Path(out).stem}__obj{obj_id}__{obj['name']}"
            writer_pool.submit(write_img, base + "_crop.png", obj['crop'])
            writer_pool.submit(write_img, pmask + "_mcrop.png", obj['masked_crop'])
            writer_pool.submit(write_img, cpmask + "_mcrop_e.png", obj['masked_crop'])

def main():

    parser = argparse.ArgumentParser(description="Extracts moving objects from a fixed background")

    #-----------------------------
    # EDIT FIELD MODE

    parser.add_argument('-i', '--input', type=str, required=True, help="""Video files""")
    parser.add_argument("-a", "--min_area", default=5000, type=int, help="""Minimum object area (in pixels), default = 5000""")
    parser.add_argument('-H', '--max_h', type=int, default=1000, help="""Maximum object height (in pixels)""")
    parser.add_argument("-W", "--max_w", default=1000, type=int, help="""Maximum object width (in pixels)""")
    parser.add_argument("-r", "--resize", default=0.25, type=float, help="""Resize factor""")
    parser.add_argument("-n", "--num_samples", default=10, type=int, help="""Number of images to keep per specimen""")
    parser.add_argument("-d", "--delta", default=10, type=float, help="""Percentage of deviation from the background, per-channel LAB tolerance (default 10, increase the value for less sensitivity)""")
    parser.add_argument("-D", "--drawing", action='store_true', help="""drawing or not""")
    parser.add_argument("-l", "--low_fps", action='store_true', help="""Halving framerate""")
    parser.add_argument("-T", "--threads", default=8, type=int, help="""Number of threads of opencv""")
    parser.add_argument("-c", "--clahe", action='store_true', help="""Apply CLAHE""")
    parser.add_argument("--max_aspect", default=0, type=float, help="""Maximum elongation (long side / short side) of an object, e.g. 6 to drop thin edge strips and fibres (default 0 = off)""")
    parser.add_argument("--label", default="Oribatida", type=str, help="""Label drawn next to each box in the annotated video (default Oribatida)""")
    parser.add_argument("--select", default="best", choices=["best", "even"], help="""Crops saved per track: 'best' (default) skips detections merged with another object and keeps the sharpest crop of each time segment, 'even' keeps evenly spaced crops (previous behaviour)""")
    parser.add_argument("--split", action='store_true', help="""Split components that contain several touching objects""")
    parser.add_argument("--split_core", default=0.5, type=float, help="""Core threshold for --split, as a fraction of the largest distance to the background (default 0.5, lower = fewer splits)""")
    parser.add_argument("--close", default=5, type=int, help="""Kernel size of the closing that reconnects appendages; it can also fuse close objects (default 5, 0 = off)""")
    parser.add_argument("--pad", default=0, type=float, help="""Margin around each crop, as a fraction of the object's longer side (default 0)""")
    parser.add_argument("-b", "--bg_model", default='median', choices=['median', 'frame', 'temporal'], help="""Background model: 'median' (scalar median color, default), 'frame' (first frame image), 'temporal' (per-pixel median over --bg_frames)""")
    parser.add_argument("--bg_frames", default=15, type=int, help="""Frames to collect for 'temporal' background model (default 15, watch memory usage)""")

    args = parser.parse_args()
    cv2.setNumThreads(args.threads)
    extract_obj(args)

if __name__ == "__main__":
    main()
