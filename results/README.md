# SediDigi/results

Segmentation results and visualisations for the project videos. Each run lives in
its own dated folder; the raw videos themselves are kept on Google Drive (too large
for GitHub).

## Runs

| Folder | Content |
|---|---|
| [`2026-10-03_bg_segmentation_v0_1/`](2026-10-03_bg_segmentation_v0_1/) | `bg_segmentation_v0_1.py` on all six videos (described below) |
| [`2026-10-03_chromatic_segmentation_07072026/`](2026-10-03_chromatic_segmentation_07072026/) | `chromatic_segmentation_07072026.py` on the same six videos |
| [`2026-10-03_readme_use_cases_BTK2_26/`](2026-10-03_readme_use_cases_BTK2_26/) | the remaining use cases of `README_for_Students.md` (defaults, `-b frame`, `-l`, `-c`) on BTK2_26 |
| [`COMPARISON.md`](COMPARISON.md) | comparison of the two scripts |

## Folder layout

```
results/
├── make_visualizations.py                 # builds the visualizations/ folder of a run
└── <date>_<script>/
    ├── <video>/base/                      # original object crops
    ├── <video>/pmask/                     # crops with the background replaced by magenta
    ├── <video>/cpmask/                    # same content as pmask/
    ├── <video>__annot.mp4                 # annotated video (boxes, track IDs, mask outlines)
    └── visualizations/
        ├── <video>__contact_sheet.jpg     # one tile per track ID: "ID  WxH" (middle crop)
        ├── <video>__annot_frames.jpg      # four frames from the annotated video
        ├── <video>__tracks.csv            # per track: crops, first/last frame, median size
        └── summary.csv                    # one line per video
```

Rebuild the visualisations of a run with:

```bash
python results/make_visualizations.py results/<run folder>
```

## 2026-10-03 — `bg_segmentation_v0_1.py`

Command used for every video:

```bash
python segmentation/bg_segmentation_v0_1.py -i <video> -b temporal --bg_frames 15 -d 10 -a 1500 --max_aspect 6 -D --label <label>
```

`--label Oribatida` for the BTK2 videos, `--label Collembola` for BTK1 and
`--label Object` for the mixed sample BTKM3_1. The two long videos (BTK1_55,
BTKM3_1) were run with `-l` (every second frame) to keep memory use and run time down.

| Video | Organism | Format | Frames | Run time | Tracks | Crops | Median crop (w×h px) |
|---|---|---|---|---|---|---|---|
| BTK1_20__Pseudosinella_alba__FUNSOIL__bg1__01.avi | Collembola (*Pseudosinella alba*) | MJPEG 4032×3040, 21 fps | 1760 | 9.1 min | 59 | 613 | 108×125 |
| BTK2_12__Ori_23_N__Funsoil__bg1__01.mov | Oribatida | ProRes 3840×2160, 14.4 fps | 1032 | 4.0 min | 68 | 723 | 70×74 |
| BTK2_16__Ori_15_N__001__V0.MOV | Oribatida | HEVC 3840×2160, 29.97 fps | 540 | 2.9 min | 79 | 769 | 121×137 |
| BTK2_26__Ori_29_N__001__V0.MOV | Oribatida | HEVC 3840×2160, 29.97 fps | 810 | 3.2 min | 38 | 434 | 200×194 |
| BTK1_55__Isotoma_viridis__V1__001.MOV | Collembola (*Isotoma viridis*) | H.264 3840×2160, 29.97 fps | 9510 | 31.3 min | 167 | 1542 | 54×96 |
| BTKM3_1__001.MOV | mixed soil sample | H.264 3840×2160, 29.97 fps | 7110 | 33.8 min | 256 | 2597 | 81×102 |

Run times were measured on a Windows laptop with CPU decoding, before multi-threaded
decoding was enabled (see [the use-case report](2026-10-03_readme_use_cases_BTK2_26/README.md#decoding-speed));
current versions of the scripts are faster.

### Observations (visual check of the contact sheets)

- **BTK2_26** — clean: every track is a whole mite; one crop holds two touching mites.
- **BTK2_12** — very good: almost all tracks are single mites. A few tracks are
  white debris, one holds two touching mites and one a mite plus a fibre.
- **BTK2_16** — mostly good, but the mites are dense: about ten crops hold 2–4
  touching mites, and a few specimens are out of focus.
- **BTK1_20** — springtails are captured well, including legs and antennae.
- **BTK1_55** — mostly springtails; a few tracks are fibres, white fluff or debris.
- **BTKM3_1** — every moving object is extracted: Oribatida, springtails, other
  small arthropods and many soil/debris particles, plus some out-of-focus
  particles. The debris is real material in the sample and has to be sorted out
  during identification.

`--max_aspect 6` removed exactly the two elongated artefacts seen without it (a
cuvette-edge strip in BTK1, 17×270 px, and a fibre in BTK2_16, 27×195 px); the most
elongated real specimen measured 4.3:1. A track counts each time a specimen is
(re-)acquired by SORT, so the number of tracks is an upper bound on the number of
individuals.
