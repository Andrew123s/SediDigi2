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

`--label Oribatida` for the BTK2 videos, `--label Collembola` for BTK1 and
`--label Object` for the mixed sample BTKM3_1. The two long videos (BTK1_55, BTKM3_1)
were run with `-l` in addition.

| Video | Organism | Frames | Tracks | Crops |
|---|---|---|---|---|
| BTK1_20__Pseudosinella_alba__FUNSOIL__bg1__01.avi | Collembola (*Pseudosinella alba*) | 1760 | 59 | 613 |
| BTK1_55__Isotoma_viridis__V1__001.MOV | Collembola (*Isotoma viridis*) | 9510 | 167 | 1542 |
| BTK2_12__Ori_23_N__Funsoil__bg1__01.mov | Oribatida | 1032 | 68 | 723 |
| BTK2_16__Ori_15_N__001__V0.MOV | Oribatida | 540 | 79 | 769 |
| BTK2_26__Ori_29_N__001__V0.MOV | Oribatida | 810 | 38 | 434 |
| BTKM3_1__001.MOV | mixed soil sample | 7110 | 256 | 2597 |
