# README use cases on BTK2_26

The commands from `segmentation/README_for_Students.md` that were not yet covered by
the main runs, executed on `BTK2_26__Ori_29_N__001__V0.MOV` (Oribatida, HEVC
3840×2160, 29.97 fps, 810 frames). `-D` was added to every command so that an
annotated video is available for checking; it does not change the crops.

Reference: the tuned run of the same video in
[`../2026-10-03_bg_segmentation_v0_1/`](../2026-10-03_bg_segmentation_v0_1/)
(`-b temporal --bg_frames 15 -d 10 -a 1500 --max_aspect 6`): 38 tracks, 434 crops,
all whole mites, one crop with two touching mites.

| Folder | README use case | Command options | Tracks | Crops | Run time |
|---|---|---|---|---|---|
| `uc1_defaults/` | 1 — quick start | *(none)* | 38 | 432 | 6.7 min |
| `uc3_frame/` | 3 — structured background | `-b frame` | 38 | 434 | 4.9 min |
| `uc4_temporal_lowfps/` | 4 — smaller, faster objects | `-b temporal --bg_frames 10 -a 1500 -l` | 26 | 222 | 3.4 min → 1.5 min* |
| `clahe/` | option `-c` | `-b temporal --bg_frames 15 -d 10 -a 1500 --max_aspect 6 -c` | 49 | 478 | 5.3 min |

\* after enabling multi-threaded decoding, see below.

## Observations (visual check of the crops)

- **Use case 1 (defaults)** — works out of the box on this video: the same 38 mites
  as the tuned run. The mites in BTK2_26 are large (about 200×200 px), so the
  default `-a 5000` is fine here; in BTK2_12 (mites about 70×75 px) it would drop
  them.
- **Use case 3 (`-b frame`)** — identical result to use case 1. The first frame of
  BTK2_26 is free of mites, which is the condition the README names for this model.
- **Use case 4 (`-l`)** — all crops are mites, but fewer tracks and crops are kept
  (half the frames are processed) and 4 of 26 tracks show two touching mites in
  the middle crop (1 of 38 in the reference). The mites in this video move slowly,
  so halving the frame rate is not needed for tracking here.
- **Option `-c` (CLAHE)** — worse on this video: 2 empty-background tracks
  (26, 107), 2 faint fibres (133, 141) and more crops with 2–4 merged mites
  (43, 45, 52, 147). BTK2_26 is evenly lit; the README recommends `-c` for *uneven*
  lighting only, and this run confirms that it should not be used otherwise.

## Decoding speed

Use case 4 was originally not faster than the reference run (201 s vs 190 s),
although the README describes `-l` as faster. Profiling showed that decoding the 4K
HEVC video was the bottleneck: `-l` skips the processing of every second frame, but
every frame still has to be decoded. The decoder ran single-threaded (PyAV default
`SLICE` threading); both scripts now enable frame threading
(`stream.thread_type = "AUTO"`).

Re-running with this change produced **byte-identical crops** and:

| Run | Before | After |
|---|---|---|
| Reference (`-b temporal ... --max_aspect 6`) | 190 s | 162 s |
| Use case 4 (`-l`) | 201 s | 91 s |

The run times in the tables above and in the other result folders were measured
before this change.
