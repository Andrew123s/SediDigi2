#!/usr/bin/env python

"""
Build visual summaries for the output of bg_segmentation_v0_1.py.

For every result folder (one per video, containing base/, pmask/, cpmask/) it writes
into <results_dir>/visualizations/:

- <video>__contact_sheet.jpg  one tile per track ID (middle crop), labelled "ID WxH"
- <video>__annot_frames.jpg   2x2 grid of frames from <video>__annot.mp4 (if present)
- <video>__tracks.csv         per track: number of saved crops, first/last frame, median crop size

and a summary.csv with one line per video.

Usage:
    python make_visualizations.py <results_dir>
"""

import argparse
import csv
import re
from pathlib import Path

import av
import cv2
import numpy as np

NAME_RE = re.compile(r"__obj(\d+)__f(\d+)__x(\d+)__y(\d+)_crop\.png$")


def load_tracks(base_dir):
    tracks = {}
    for f in sorted(base_dir.glob("*_crop.png")):
        m = NAME_RE.search(f.name)
        if m:
            tracks.setdefault(int(m[1]), []).append((int(m[2]), f))
    return tracks


def contact_sheet(tracks, tile=160, cols=10):
    tiles = []
    for obj_id in sorted(tracks):
        crops = tracks[obj_id]
        img = cv2.imread(str(crops[len(crops) // 2][1]))
        h, w = img.shape[:2]
        t = np.zeros((tile, tile, 3), np.uint8)
        s = (tile - 14) / max(h, w)
        r = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        t[:r.shape[0], :r.shape[1]] = r
        cv2.putText(t, f"{obj_id}  {w}x{h}", (3, tile - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
        tiles.append(t)
    while len(tiles) % cols:
        tiles.append(np.zeros((tile, tile, 3), np.uint8))
    return np.vstack([np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)])


def annot_frames(video, n=4):
    # Two passes: count frames, then keep only the picked ones (full decode would not fit in memory)
    with av.open(str(video)) as c:
        total = sum(1 for _ in c.demux(video=0)) - 1   # last packet is the empty flush packet
    idx = np.linspace(total * 0.1, total * 0.9, n).astype(int)
    with av.open(str(video)) as c:
        picks = [f.to_ndarray(format="bgr24") for i, f in enumerate(c.decode(video=0)) if i in set(idx)]
    for i, img in zip(idx, picks):
        cv2.putText(img, f"frame {i}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
    return np.vstack([np.hstack(picks[:2]), np.hstack(picks[2:])])


def main():
    parser = argparse.ArgumentParser(description="Visual summaries of segmentation results")
    parser.add_argument("results_dir", type=Path)
    args = parser.parse_args()

    out = args.results_dir / "visualizations"
    out.mkdir(exist_ok=True)
    summary = []

    for d in sorted(p for p in args.results_dir.iterdir() if (p / "base").is_dir()):
        tracks = load_tracks(d / "base")
        if not tracks:
            continue
        cv2.imwrite(str(out / f"{d.name}__contact_sheet.jpg"), contact_sheet(tracks), [cv2.IMWRITE_JPEG_QUALITY, 85])

        annot = args.results_dir / f"{d.name}__annot.mp4"
        if annot.exists():
            cv2.imwrite(str(out / f"{d.name}__annot_frames.jpg"), annot_frames(annot), [cv2.IMWRITE_JPEG_QUALITY, 85])

        rows = []
        for obj_id in sorted(tracks):
            sizes = [cv2.imread(str(f)).shape[:2] for _, f in tracks[obj_id]]
            frames = [fr for fr, _ in tracks[obj_id]]
            hs, ws = zip(*sizes)
            rows.append([obj_id, len(frames), min(frames), max(frames), int(np.median(ws)), int(np.median(hs))])
        with open(out / f"{d.name}__tracks.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["track_id", "crops", "first_frame", "last_frame", "median_w_px", "median_h_px"])
            w.writerows(rows)

        n_crops = sum(r[1] for r in rows)
        summary.append([d.name, len(rows), n_crops,
                        int(np.median([r[4] for r in rows])), int(np.median([r[5] for r in rows]))])
        print(f"{d.name}: {len(rows)} tracks, {n_crops} crops")

    with open(out / "summary.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["video", "tracks", "crops", "median_w_px", "median_h_px"])
        w.writerows(summary)


if __name__ == "__main__":
    main()
