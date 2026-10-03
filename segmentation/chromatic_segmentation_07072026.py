#!/usr/bin/env python

"""
The script implements a video-based object extraction and tracking pipeline designed for organisms moving over a uniform, stationary background (e.g., mites or insects). Its goal is to detect each individual, track it across frames, and save a representative set of cropped images for each tracked specimen.

Quick and dirty. Next step would be to GPU-accelerate this if keeping with the 30 fps
"""

import argparse
import glob
import os
import sys
from pathlib import Path
import time

#----------------------
from sort.sort import *

#----------------------
import av
import cv2
import numpy as np
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
        except av.AVError:
            continue

    # Fallback: software decode (always works)
    return av.open(path)


def extract_obj(args):
    """
    Automatically detect the background on each frames, using color range selection,
    and return the segmentation (as cv2 contours) of objects in each frame
    in a dictionnary fitting the structure of the COCO JSON format.
    """

    video_path = Path(args.input) # 0 for cam

    min_area = args.min_area  # minimum object area (in pixels)
    max_h = args.max_h # maximum object height (in pixels)
    max_w = args.max_w # maximum object width (in pixels)
    resize_factor =  args.resize
    n = args.num_samples
    d = args.delta

    # --- Make crops output directory
    out = video_path.with_suffix('')
    Path(out).mkdir(parents=True, exist_ok=True)
    Path(f"{out}/base").mkdir(parents=True, exist_ok=True)
    Path(f"{out}/pmask").mkdir(parents=True, exist_ok=True)
    Path(f"{out}/cpmask").mkdir(parents=True, exist_ok=True)

    # --- Setup capture (CV2) ---
    #cap = cv2.VideoCapture(str(video_path))
    #fps = cap.get(cv2.CAP_PROP_FPS)
    #twidth = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    #theight = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    #n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # --- Setup capture (AV) ---
    container = open_video(video_path)
    stream = container.streams.video[0]
    fps = int(stream.average_rate)

    if args.low_fps:
        fps = int(fps/2)

    twidth = stream.codec_context.width
    theight = stream.codec_context.height
    n_frames = stream.frames

    width  = int(twidth * resize_factor)
    height = int(theight * resize_factor)


    # --- Video writer setup ---
    if args.drawing:
        # --- CV2 ---
        #fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        #out_vid = cv2.VideoWriter(f"{out}__annot.mp4", fourcc, fps, (width, height))

        # --- AV ---
        print(f"opening {out}__annot.mp4")
        out_cont = av.open(f"{out}__annot.mp4", mode="w")
        o_stream = out_cont.add_stream("h264", rate=fps)
        o_stream.width = width
        o_stream.height = height
        o_stream.pix_fmt = "yuv420p"


    color = [0, 215, 255] # Color for drawing annotations

    print('Running mask detection based on invert background color selection')

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5,5))

    mot_tracker = Sort()
    tracked_objects = dict()

    get_median = True # To switch off the median computation after the first frame.

    color_mask = np.zeros((int(height), int(width), 3), np.uint8) # Allocating drawing layer
    mask = np.zeros((int(theight), int(twidth)), np.uint8) # Allocating mask layer

    frame_id = 0

    for i, frame in enumerate(tqdm(container.decode(video=0), total=n_frames, desc="Processing frames")):

        if args.low_fps and i % 2 == 1:   # skip odd frames
            continue

        #loop_start_time = time.time()

        frame_id += 1

        #start_time = time.time()

        #ret, img = cap.read()
        #if not ret:
        #   break

        img = frame.to_ndarray(format="bgr24")

        #print(f"Reading frame -- {(time.time() - start_time)*1000:.2f} ms")
        #start_time = time.time()

        lab_img = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)

        if  args.clahe:

            # Split channels
            l, a, b = cv2.split(lab_img)
            # Apply CLAHE on L channel only
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            cl = clahe.apply(l)
            # Merge back
            lab_clahe = cv2.merge((cl, a, b))
            # Convert back to BGR
            lab_img = cv2.cvtColor(lab_clahe, cv2.COLOR_LAB2BGR)


        #hsv_img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # Getting the median color of the first frame, defined as the central background color.
        # This computation is slow (~100ms), hence is done only on the first frame.
        # This means that the background color must remain stable during the video capture.
        if get_median:

            median_lab_color = np.median(lab_img, axis=[0,1])

            # cv2 HSV range to regular HSV range conversion formulas
            #H=int(179*d/100)
            #S=int(255*d/100)
            #V=int(255*d/100)

            # cv2 LAB range
            L=int(255*d/100)
            a=int(255*d/100)
            b=int(255*d/100)

            low_color = median_lab_color - (L,a,b)
            high_color = median_lab_color + (L,a,b)

            get_median = False

        mask[:] = cv2.inRange(lab_img, low_color, high_color)
        fgmask = cv2.bitwise_not(mask)

        #print(f"Mask from color substraction -- {(time.time() - start_time)*1000:.2f} ms")
        #start_time = time.time()

        # Closing the shape
        # fgmask = cv2.erode(fgmask, kernel, iterations=1)
        # fgmask = cv2.dilate(fgmask, kernel, iterations=1)

        # Recovering lost parts (appendages) - but unfortunatly may also fuse close objects.
        # Gut feeling = untested. Cost 4.3 ms
        fgmask = cv2.dilate(fgmask, kernel, iterations=1)
        fgmask = cv2.erode(fgmask, kernel, iterations=1)

        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(fgmask) # Get instances from fgmask

        #print(f"Operations on mask and instance segmentation -- {(time.time() - start_time)*1000:.2f} ms")
        #start_time = time.time()

        detections = list()  # to keep list of bbox
        crops = list()       # to keep object crops (img)
        masks = list()       # to keep object crops (masks)
        names = list()       # to keep object coord (frame n + loc)
        obj_id = list()      # to keep object_id (tracking)
        masked_crop = list() # to keep object crops (img with masked background)
        mask_objs = list()   # to keep the resized full img object masks if drawing
        # Loop into the found segments.

        for obj in range(1, num_labels):

            x, y, w, h, area = stats[obj]

            # Filter on min size, max height, and remove if close to top and bottom edge.
            if (area > min_area) and (h < max_h) and (y > 20) and ((y+h) < (theight-20)):

                detections.append([x,y, x+w, y+h, None])            # saving the detection bbox for tracking
                mask_obj = (labels == obj).astype(np.uint8) * 255   # frame-wide mask of the object
                names.append(f"f{frame_id:05d}__x{x}__y{y}")        # naming the object by frame and location

                # Collecting the object crops and the mask crops, and keep in memory.
                # I keep everything in memory until the end of the video. Then the tracking is done,
                # and only 10 crops + masks of each objects are written.

                img_crop = img[y:y+h, x:x+w]
                mask_crop = mask_obj[y:y+h, x:x+w]
                masks.append(mask_crop.copy())
                crops.append(img_crop.copy())

                # Masking the background of the object crop
                bgc = np.array([210, 100, 150], dtype=np.uint8)
                mcrops = img_crop.copy()
                mcrops[mask_crop == 0] = bgc
                masked_crop.append(mcrops)

                if args.drawing:
                    mask_objs.append(
                        cv2.resize(mask_obj, (width, height), interpolation=cv2.INTER_AREA)
                        )

        #print(f"Saving crops of found segments in memory -- {(time.time() - start_time)*1000:.2f} ms")
        #start_time = time.time()

        if args.drawing:
            color_mask[:] = 0 # Reset the mask drawing layer
            # Make drawing layer (= copy of scaled down image)
            img_d = cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA)

            # Drawing
            for i in range(len(detections)):
                # Draw scaled bbox and cosmetic label
                rdet = [round(e * resize_factor) for e in detections[i][:4]]
                cv2.rectangle(img_d, (rdet[0],rdet[1]), (rdet[2],rdet[3]), color, round(5*resize_factor))
                cv2.putText(img_d, f"Oribatida", (rdet[0], rdet[1]-5), cv2.FONT_HERSHEY_SIMPLEX, 2*resize_factor, color, int(6*resize_factor))

                # Make border of the mask and draw on the mask layer
                dilated = cv2.dilate(mask_objs[i], None, iterations=1)
                eroded  = cv2.erode(mask_objs[i], None, iterations=1)
                border = dilated - mask_objs[i]
                color_mask[border > 0] = color

        #print(f"Drawing -- {(time.time() - start_time)*1000:.2f} ms")
        #start_time = time.time()

        # Tracking objects
        if len(detections) == 0:
            track_bbs_ids = mot_tracker.update(np.empty((0, 5)))
            #print('no detections')
        else:
            detections = np.array(detections)
            track_bbs_ids = mot_tracker.update(detections)
            for i in range(0, len(track_bbs_ids)):
                detect = track_bbs_ids[i]
                obj_id = int(detect[4])
                if obj_id in tracked_objects:
                    tracked_objects[obj_id].append({'crop': crops[i], 'mask': masks[i], 'masked_crop' : masked_crop[i], 'name': names[i]})
                else:
                    tracked_objects[obj_id] = [{'crop': crops[i], 'mask': masks[i], 'masked_crop' : masked_crop[i], 'name': names[i]}]

                # Drawing the tracked object id
                if args.drawing:
                    cv2.putText(img_d, f"{int(detect[4])}",
                                (int(detect[2] * resize_factor), int(detect[3] * resize_factor)+5),
                                cv2.FONT_HERSHEY_SIMPLEX, 2*resize_factor, color, int(6*resize_factor))

        #print(f"Tracking object -- {(time.time() - start_time)*1000:.2f} ms")
        #start_time = time.time()

        if args.drawing:

            mask_binary = np.any(color_mask != 0, axis=2)
            img_d[mask_binary] = (
                        color_mask[mask_binary]
                        ).astype(np.uint8)


            av_frame = av.VideoFrame.from_ndarray(img_d, format="bgr24")
            packet = o_stream.encode(av_frame)
            if packet:
                out_cont.mux(packet)

        #print(f"Writing annotated frame to video out -- {(time.time() - start_time)*1000:.2f} ms")
        #print(f"Frame processed in -- {(time.time() - loop_start_time)*1000:.2f} ms")

    container.close()
    if args.drawing:
        out_cont.close()

    #start_time = time.time()
    print("Writing crop")

    # Parallelizing crop writing
    writer_pool = ThreadPoolExecutor(max_workers=args.threads)

    def write_img(path, img):
        cv2.imwrite(path, img)

    for obj_id in tracked_objects:
        # Only 10 crops are saved per track object along the fall sequences
        step = len(tracked_objects[obj_id]) // n
        if step == 0:
            step = 1

        for obj in tracked_objects[obj_id][::step]:
            base = f"{out}/base/{Path(out).stem}__obj{obj_id}__{obj['name']}"
            pmask = f"{out}/pmask/{Path(out).stem}__obj{obj_id}__{obj['name']}"
            cpmask = f"{out}/cpmask/{Path(out).stem}__obj{obj_id}__{obj['name']}"
            #cv2.imwrite(base + "_mask.png", obj['mask'])
            writer_pool.submit(write_img, base + "_crop.png", obj['crop'])
            writer_pool.submit(write_img, pmask + "_mcrop.png", obj['masked_crop'])
            writer_pool.submit(write_img, cpmask + "_mcrop_e.png", obj['masked_crop'])

    #print(f"Crops writing done -- {(time.time() - start_time)*1000:.2f} ms")

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
    parser.add_argument("-d", "--delta", default=10, type=float, help="""Percentage of deviation from median background (default 10, increase the value for less sensitivity)""")
    parser.add_argument("-D", "--drawing", action='store_true', help="""drawing or not""")
    parser.add_argument("-l", "--low_fps", action='store_true', help="""Halving framerate""")
    parser.add_argument("-T", "--threads", default=8, type=int, help="""Number of threads of opencv""")
    parser.add_argument("-c", "--clahe", action='store_true', help="""Apply CLAHE""")

    args = parser.parse_args()
    cv2.setNumThreads(args.threads)
    extract_obj(args)

if __name__ == "__main__":
    main()
