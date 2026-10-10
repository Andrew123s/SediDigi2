# README for Students

This is a practical guide to `bg_segmentation_v0_1.py` — how to run it, what it does,
and how to fix the most common problems.

Software setup is described in [README.md](README.md). 
This guide assumes that the setup is already done.

---

## What is this script?

`bg_segmentation_v0_1.py` extracts **moving objects** (e.g. soil mites /
Oribatida) from videos recorded against a **static background**. For every
object it:

1. detects it,
2. tracks it across the frames,
3. saves a small set of cropped images of it.

You get local images for each individual specimen, ready for later
identification or analysis.

---

## Your first run

Open a terminal inside this folder and run:

```bash
python bg_segmentation_v0_1.py -i <video filename>
```

That is all. The script works out of the box with default settings.

**What happens next:**

- A progress bar appears while the video is processed.
- A new folder is created next to your video (named after the video without
  the file extension).
- Inside it you find `base/`, `pmask/` and `cpmask/` with the saved object
  crops (see [The output](#the-output-what-do-you-get)).
- Annotated videos (`__annot.mp4`) are only produced if you add the
  `-D` flag.

---

## How it works behind the scenes

This short background makes the options below much easier to understand.

1. **Background model** — The script needs to know what the background looks
   like. Three ways of building this are available; see
   [Choosing a background model](#choosing-a-background-model).
2. **Colour comparison (LAB space)** — Each frame is compared to the background
   model in the LAB colour space. Pixels that differ by more than the tolerance
   `delta` (default 10 %) are marked as *foreground*.
3. **Foreground mask** — All foreground pixels form a black-and-white mask per
   frame. Between objects touching each other would be one blob.
4. **Detections** — The mask is cleaned up (small noise removed) and
   *connected components* become detections, i.e. potential objects.
5. **Tracking (SORT)** — Detections are linked across frames into tracks. Each
   track gets a stable ID. Note: a track is only kept after the object was
   detected in **at least 3 consecutive frames**.
6. **Crop saving** — For each track, a limited number (`-n`, default 10) of
   representative crops is written at the end of the video.

---

## Choosing a background model

Use `-b` to select the model: `-b median`, `-b frame` or `-b temporal`.

| Model | How the background is defined | Good for | Watch out for |
|---|---|---|---|
| `median` *(default)* | The average colour of the first frame, one single value | Uniform, stable backgrounds; the quickest, no extra settings | Gratings, gradients or colour drift on the background |
| `frame` | The first frame itself, pixel by pixel | Structured backgrounds with uneven lighting | The first frame **must be free of objects**, otherwise they become part of the background |
| `temporal` | The pixel-by-pixel median over the first `--bg_frames` frames | Noisy backgrounds or slow "floaters" in the first frames; the most robust choice | Needs `--bg_frames` full frames in memory; later colour drift is not corrected |

If an object passes over the background during the first frames, `median` and
`frame` may silently absorb it. `temporal` is safest for recordings like the
BTK2 videos.

---

## Most important options

| Option | Meaning | When to change it |
|---|---|---|
| `-i, --input` | Path to the video file | Always required |
| `-b, --bg_model` | `median`, `frame` or `temporal` | When the background is not uniform (`frame`) or not stable (`temporal`) |
| `-d, --delta` | Tolerance per LAB channel, in % (default 10) | Objects missed → **raise** it; too much noise → **lower** it |
| `-a, --min_area` | Minimum object area in pixels (default 5000) | Your objects are smaller than the default (e.g. mites) → **lower it** |
| `-H, --max_h` | Maximum object height in pixels (default 1000) | Long structures span the whole frame → lower it |
| `-W, --max_w` | Maximum object width in pixels (default 1000) | Wide structures span the frame → lower it |
| `--max_aspect` | Maximum elongation, long side / short side (default 0 = off) | Thin edge strips or fibres are saved as objects → set it, e.g. `--max_aspect 6` |
| `--label` | Label drawn in the annotated video (default `Oribatida`) | Other organisms, e.g. `--label Collembola` |
| `--split` | Splits blobs of touching objects into single objects (default off) | Mites touching each other end up in one crop → set it; not for springtails |
| `--select` | Which crops are saved per track: `best` (default) skips merged moments and keeps the sharpest crops, `even` keeps evenly spaced crops | Normally keep `best` |
| `--bg_frames` | Frames collected for `temporal` (default 15) | More → more robust but needs more memory |
| `-n, --num_samples` | Crops saved per track (default 10) | Save more/less per specimen |
| `-D, --drawing` | Also writes an annotated video (`__annot.mp4`) | When you want a visual check of detection + tracking |
| `-l, --low_fps` | Processes every second frame only | Faster processing and fewer tracking breaks for very fast objects |
| `-c, --clahe` | Improves local contrast before subtraction | Uneven lighting in the video |

---

## The output — what do you get?

Next to your video, a folder is created with three sub-folders:

- **`base/`** — the original crop image of the object (unchanged).
- **`pmask/`** — the crop where the background was replaced by a magenta colour
  (the object stays in original colour).
- **`cpmask/`** — the same masked crop as `pmask/` (content identical).

File names follow this pattern:

```
<video-stem>__obj<track-id>__f<frame>__x<x>__y<y>_crop.png
```

- `obj<track-id>` — the tracking ID (same object → same ID across frames).
- `f<frame>__x<x>__y<y>` — frame number and crop position, so you can trace
  where an image came from.

With `-D` you additionally get `<video>__annot.mp4`: the video with bounding
boxes, track IDs and colour masks drawn in.

---

## Typical use cases

**1. Quick start — just run it**

```bash
python bg_segmentation_v0_1.py -i <video filename>
```

Default median model, no tuning. Best first step.

**2. Quick start plus a visual check**

```bash
python bg_segmentation_v0_1.py -i <video filename> -D
```

Adds the annotated video so you can eyeball whether everything was detected.

**3. Structured background**

```bash
python bg_segmentation_v0_1.py -i <video filename> -b frame
```

Uses the first frame as background reference. Only if frame 0 is clean.

**4. Smaller, faster objects (e.g. mites)**

```bash
python bg_segmentation_v0_1.py -i <video filename> -b temporal --bg_frames 10 -a 1500 -l
```

Temporal model (stability), smaller minimum area, and halved frame rate to keep
fast objects tracked.

**5. Concrete example from the project (BTK2)**

```bash
python bg_segmentation_v0_1.py -i BTK2_12__Ori_23_N__Funsoil__bg1__01.mov -b temporal --bg_frames 15 -d 10 -a 1500 -D
```

**6. Tested settings for all project videos (BTK1 and BTK2)**

```bash
python bg_segmentation_v0_1.py -i <video filename> -b temporal --bg_frames 15 -d 10 -a 1500 --max_aspect 6 -D
```

Same as example 5, plus `--max_aspect 6`, which drops thin cuvette-edge strips
and fibres. For the mite videos (BTK2) add `--split`; for the springtail videos
(BTK1) add `--label Collembola` instead. Example results for all six videos are in
the `Andrew_results/` folder of the repository.

---

## Common mistakes

**My output folders are empty.**

The most likely causes:

- `-a` (`--min_area`) is too large for your objects. Object sizes vary wildly
  between videos — check the filter (default 5000 px) and lower it, e.g.
  `-a 1500`.
- You used `-b frame` and frame 0 already contained an object. The object
  becomes "background", so it is never detected. Use another model or a
  different first frame.
- `temporal` with too few frames (`--bg_frames` very low) can absorb an object
  that stays still during collection.

**Everything is detected as one giant blob.**

The tolerance `delta` is too permissive, or the foreground noise is huge.
Lower `-d` and check the mask sizes. A single blob that covers almost the whole
frame is normally filtered out by `-H`/`-a`, leading back to the empty-output
problem above.

**An object disappears mid-video / gets two IDs.**

SORT breaks the track when an association is too weak. Very fast objects, or a
low frame rate, are typical causes. Try `-l` (halve the effective fps) or
record at a higher frame rate. Note that every track also needs ≥3 consecutive
detections before it is kept at all.

**Thin strips along the cuvette edge or fibres are saved as objects.**

If the camera or cuvette shifts slightly, its edges differ from the background
model and show up as long, thin detections. Add `--max_aspect 6`: real
specimens are much less elongated than these strips.

**Two or more specimens end up in one crop.**

Specimens that touch form a single blob in the mask and are saved as one
object. For mites, add `--split`: it separates blobs that consist of several
round bodies. It does not work for springtails (it cuts them at the neck) or
for specimens lying on top of each other; sort those crops out by hand.

**The script eats a lot of memory.**

The `temporal` model keeps `--bg_frames` full-resolution frames in memory.
Reduce `--bg_frames` (e.g. 10) or use `median`.

---

## Feedback

Are the results not as expected? Did an error message appear? The script has
always worked in our environment, so difficulties are usually small and
quickly resolved.

Send the following information together with your request, then I can help you
right away:

- the exact command you used, including all options
- the error message or relevant console output (copy & paste, please no
  screenshots)
- what exactly looks wrong in the result (e.g. empty folders, missing objects,
  wrong masks)
- if possible, a short description of the video (object size, background,
  recording conditions), a screenshot will be welcome.

**Contact:** 

André Seeliger  

Mail: a.seeliger@hszg.de  
Phone: +49 3583 6124772

Hochschule Zittau/Görlitz  
Institut für Prozesstechnik, Prozessautomatisierung und Messtechnik (IPM)  
Fachgebiet Kerntechnik/Soft Computing  
Theodor-Körner-Allee 16  
02763 Zittau  


## References

- [SORT: Simple Online and Realtime Tracking](https://arxiv.org/abs/1602.00763)
- [sort-tracker-py (PyPI)](https://pypi.org/project/sort-tracker-py/)
- [abewley/sort (GitHub)](https://github.com/abewley/sort)
- [Main README](README.md) — setup, full option reference, background model details