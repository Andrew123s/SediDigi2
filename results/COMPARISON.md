# Comparison: `bg_segmentation_v0_1.py` vs `chromatic_segmentation_07072026.py`

Both scripts share the same pipeline (LAB colour comparison → mask → connected
components → SORT tracking → crops). The difference is the background model:

- `chromatic_segmentation_07072026.py` always uses **one median colour** taken from
  the first frame (equivalent to `-b median`).
- `bg_segmentation_v0_1.py` was run with `-b temporal`: a **per-pixel** median over
  the first 15 frames, so static structures in the background are learned as
  background.

All other settings were identical: `-d 10 -a 1500 --max_aspect 6 -D`. The two long
videos (BTK1_55, BTKM3_1) were additionally run with `-l` (every second frame) by
both scripts, to keep memory use and run time down.

Result folders:
[`2026-10-03_bg_segmentation_v0_1/`](2026-10-03_bg_segmentation_v0_1/) and
[`2026-10-03_chromatic_segmentation_07072026/`](2026-10-03_chromatic_segmentation_07072026/).

## Results

| Video | Background | Tracks temporal / chromatic | Crops temporal / chromatic | Run time temporal / chromatic |
|---|---|---|---|---|
| BTK2_12 (Oribatida) | grey-blue, with lighter patches and a bright spot | 68 / **304** | 723 / **2212** | 4.0 / **32.3 min** |
| BTK2_16 (Oribatida) | even blue | 79 / 77 | 769 / 764 | 2.9 / 3.5 min |
| BTK2_26 (Oribatida) | even blue | 38 / 38 | 434 / 432 | 3.2 / 7.0 min |
| BTK1_20 (Collembola) | grey-blue, light reflections | 59 / 63 | 613 / 646 | 9.1 / 12.2 min |
| BTK1_55 (Collembola, *Isotoma viridis*) | blue with a brightness gradient, cuvette wall in view | 167 / **249** | 1542 / 1980 | 31.3 / 23.0 min |
| BTKM3_1 (mixed sample) | even blue, cuvette wall in view | 256 / 263 | 2597 / 2604 | 33.8 / 30.2 min |

Run times are single runs (before multi-threaded decoding was enabled) on a Windows
laptop that was also used for other work, so
small differences are not meaningful; the BTK2_12 difference is.

### Track quality

**BTK2_12 — clear difference.** The tracks were classified by the colour of the
object pixels (the mites are red-brown, the background is blue-grey) and checked
against the contact sheets:

| | Mite tracks | Background tracks |
|---|---|---|
| temporal | 65 | 3 |
| chromatic | 89 | **215** |

The lighter patches of the background differ from the single median colour by more
than `delta`, so the chromatic script marks them as foreground in every frame
(visible as large outlined shapes in `__annot_frames.jpg`). About 20 of these static
blobs are present per frame and are re-tracked under new IDs again and again. Mites
crossing them merge with the blob and lose their track, which is why the chromatic
run also has more (fragmented) mite tracks. The many large blobs also make it about
8× slower.

**BTK2_16 and BTK2_26 — no meaningful difference.** The background is an even blue,
so one median colour describes it well. Both scripts find the same mites; the
remaining problems (touching mites in one crop, a few out-of-focus specimens) are
the same in both.

**BTK1_20 — small difference.** Both scripts capture the same springtails. The
chromatic run adds about 5 false tracks: 3 shimmering light-reflection streaks
(tracks 1, 39, 90) and 2 empty background patches (tracks 3, 4).

**BTK1_55 — clear difference.** Tracks were checked for how much of the object area
is background blue. The chromatic run has about **70 tracks that contain only
background** (tall, narrow, empty blue crops caused by the brightness gradient
across the frame), out of 249. The temporal run has none; its only two flagged
tracks are black fibres. Apart from that, both find the same springtails, plus a
few fibres and debris particles.

**BTKM3_1 — small difference.** A mixed soil sample: both scripts extract the same
moving objects — Oribatida, springtails, other small arthropods and many
soil/debris particles (the debris is real material moving in the video and has to
be sorted out during identification). The chromatic run adds 17 empty-background
tracks.

On the two long videos the chromatic script was somewhat faster (single runs, see
the note above).

## Conclusion

- On an even background both scripts give practically the same result.
- On a background with structure or uneven brightness (BTK2_12, BTK1_55, and to a
  lesser extent BTK1_20 and BTKM3_1), the single median colour of the chromatic
  script produces many false tracks; on BTK2_12 it also fragments the real tracks
  and is about 8× slower.
- `bg_segmentation_v0_1.py -b temporal` is the better default for these recordings.
