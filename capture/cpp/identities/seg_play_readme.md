# seg_play v0.1.0

Playback tool for segmentation videos with **black background rendering**: 
pixels with luma `Y == 0` (masked background) are shown black, 
all other pixels keep their original colour.

Works with any video the live tools can read (decodebin); intended for the
recordings produced by `chrseg_live --record` and `bgseg_live --record`.

## Why this is needed

The live tools store the GPU-processed buffer "as is": the background has
`Y = 0` but the shared NV12 chroma (UV) is untouched. When such a frame is
decoded and converted YUV→RGB, the leftover chroma turns the background into a
"chroma ghost" — e.g. deep blue for the bluish background (the `B` matrix term
`1.772·(Cb−128)` dominates at zero luma).

This player fixes the playback side by neutralizing the chroma of background
blocks:

```
NV12 2x2 block chroma is shared. For every 2x2 luma block that is fully
background (all four Y bytes <= 8, tolerating JPEG round-trip noise),
its UV sample is set to neutral gray (128,128) → the block renders black.

Blocks containing at least one object pixel keep their original chroma →
object colours preserved; only the 2x2 border crossing an object edge can
show a faint colour fringe (inherent NV12 4:2:0 limitation).
```

## Pipeline

```
filesrc location="…" ! decodebin ! nvvidconv bl-output=false
  ! video/x-raw,format=NV12 ! identity(name=proc)
  ! nvvidconv ! video/x-raw(memory:NVMM),width=<W>,height=<H>
  ! nvegltransform ! nveglglessink sync=false
```

Per frame (identity handoff):

```
upload Y + UV to GPU
  → kernel_black_bg: UV=128 where 2x2 block fully background (Y<=8)
  → download modified UV back
```

Only two GPU buffers (`d_y`, `d_uv`; ~18 MB @ 4032×3040), one small kernel —
no colour conversion, no segmentation. MJPEG frames are hardware-decoded by
`nvjpegdec` via decodebin.

## Build

```bash
cmake -S identities -B identities/build && cmake --build identities/build --target seg_play
```

## Usage

```bash
./build/seg_play --input <record filename>

# scale display to full width
./build/seg_play --input <record filename> --width 1920

# timing stats
./build/seg_play <record filename> --benchmark
```

`--input <datei>` is required; a positional path is accepted as a shortcut.
Press ENTER, close the window, or reach end of file (EOS) to exit.

## Notes

- Display size: `--width` (default 1280, 4:3); processing/decode always at the
  file's native resolution.
- File mode uses a **PAUSED preroll** before PLAYING — without it decodebin's
  typefind (pull mode against filesrc) can abort with
  `typefind: Internal data stream error` (same fix as chrseg_live v0.2.1).
- Threshold `PLAY_BG_T = 8` in `play_kernels.cuh` tolerates JPEG luma noise;
  raise if near-background blocks keep a tint, lower if very dark objects
  vanish.

## Files

- `seg_play.cu` — main program
- `play_kernels.cuh` — `kernel_black_bg` (NV12 block-chroma masking)
- `CMakeLists.txt` — build config (target `seg_play`)