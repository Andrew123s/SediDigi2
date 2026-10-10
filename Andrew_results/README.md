# Andrew_results

Results of `segmentation/bg_segmentation_v0_1.py` on the six test videos.

- `segmented_videos/` — annotated videos (`<video>__annot.mp4`) with bounding boxes,
  track IDs and mask outlines.
- `crops/<video>/` — object crops per video: `base/` (original crop), `pmask/`
  (background replaced by magenta) and `cpmask/` (same content as `pmask/`).

Command used for every video:

```bash
python segmentation/bg_segmentation_v0_1.py -i <video> -b temporal --bg_frames 15 -d 10 -a 1500 --max_aspect 6 -D --label <label>
```

- BTK2 videos (Oribatida): `--label Oribatida --split`
- BTK1 videos (Collembola): `--label Collembola`
- BTKM3_1 (mixed sample): `--label Object`
- The two long videos (BTK1_55, BTKM3_1) were run with `-l` in addition.

Crops per track are chosen with the default `--select best`: detections merged with
another object are skipped and the sharpest crop of each time segment is kept (at most
10 per track).

| Video | Organism | Frames | Tracks | Crops |
|---|---|---|---|---|
| BTK1_20__Pseudosinella_alba__FUNSOIL__bg1__01.avi | Collembola (*Pseudosinella alba*) | 1760 | 59 | 548 |
| BTK1_55__Isotoma_viridis__V1__001.MOV | Collembola (*Isotoma viridis*) | 9510 | 167 | 1345 |
| BTK2_12__Ori_23_N__Funsoil__bg1__01.mov | Oribatida | 1032 | 67 | 637 |
| BTK2_16__Ori_15_N__001__V0.MOV | Oribatida | 540 | 76 | 621 |
| BTK2_26__Ori_29_N__001__V0.MOV | Oribatida | 810 | 34 | 332 |
| BTKM3_1__001.MOV | mixed soil sample | 7110 | 256 | 2261 |
