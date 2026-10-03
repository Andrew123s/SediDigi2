# SediDigi/meas

This folder holds algorithms for quantitative measurements applied to
digital images. Each algorithm is provided as a Python tool (OpenCV, NumPy)
and a C++ tool (OpenCV C++ API) with identical semantics, for reproducibility
across toolchains. Sharpness measurement ships as a command-line tool;
contour measurement ships as an embeddable library (Python module / C++
source file) that takes a binary image in memory.

## Sharpness (focus measure)

The sharpness tool computes a single scalar score per image using the
Tenengrad focus measure.

```
F = (1 / N) * sum(Ix^2 + Iy^2)
```

- `Ix`, `Iy` - Sobel gradient components (kernel 3x3) of the grayscale image
- `N` - number of pixels the measure is computed over

The score is the mean gradient energy, normalized by pixel count and
therefore comparable across resolutions and crops. A higher value indicates a
sharper image.

### Files

- **focus_measure.py** - Python CLI (OpenCV, NumPy): reads a single image
  file, computes the score over the selected region of interest and prints
  one scalar value (or a JSON object).
- **focus_measure.cpp** - C++ counterpart using the OpenCV C++ API
  (`core`, `imgproc`, `imgcodecs`); identical metric and interface.
- **CMakeLists.txt** - standalone CMake build producing the
  `focus_measure` executable.

### Command-line interface (both tools)

| Option | Description | Default |
|---|---|---|
| `image` (positional) | Path to the input image file | required |
| `--scale F` | Downscale factor applied before measuring (e.g. 0.5 halves each dimension) | `1.0` |
| `--roi {full\|center}` | Region of interest: the whole image or a centered crop | `full` |
| `--roi-fraction F` | Side length of the center crop as a fraction of the smaller image side | `0.8` |
| `--json` | Print the score as a single JSON object | off |

### Software setup

Dependencies: `python3 -m pip install opencv-python numpy` (Python) or
OpenCV `core`/`imgproc`/`imgcodecs`, CMake >= 3.10, C++17 (C++).

#### Run the Python version

```bash
python3 focus_measure.py image.png
python3 focus_measure.py image.png --scale 0.5 --roi center --json
```

#### Build and run the C++ version

```bash
cmake -S . -B build
cmake --build build

./build/focus_measure image.png
./build/focus_measure image.png --scale 0.5 --roi center --json
```

### Troubleshooting

#### Python: `ModuleNotFoundError: No module named 'cv2'`

Install OpenCV for Python as shown above, or use a virtual environment:

```bash
python3 -m venv .venv
.venv/bin/pip install opencv-python numpy
.venv/bin/python focus_measure.py image.png
```

#### C++: `Could not find a package configuration file ... OpenCVConfig.cmake`

Make sure OpenCV is installed with development headers. If you use a
custom-built OpenCV (not in the system path), point CMake at it, for example:

```bash
cmake -S . -B build -DOpenCV_DIR=/path/to/opencv/lib/cmake/opencv4
cmake --build build
```

### Notes

- Grayscale conversion is done with `cv::IMREAD_GRAYSCALE` in both
  implementations, so scores are directly comparable.
- Border handling of the Sobel operator uses OpenCV's default
  (`BORDER_DEFAULT`).

### References

- [Said Pertuz, Domenec Puig, Miguel Angel Garcia: Analysis of focus measure operators for shape-from-focus, Pattern Recognition 46 (2013) 1415-1432](https://doi.org/10.1016/j.patcog.2012.11.011)
- [Yao Sun, Stefan Duthaler, Bradley J. Nelson: Autofocusing in computer microscopy: Selecting the optimal focus algorithm, Microscopy Research and Technique 65 (2004) 139-149](https://doi.org/10.1002/jemt.20118)
- [OpenCV documentation: Sobel derivatives](https://docs.opencv.org/4.x/d2/d2c/tutorial_sobel_derivatives.html)

## Contour measurement

The contour measurement library computes geometric and intensity properties of
the regions (contours) found in a binary image. The input is an 8-bit,
single-channel image held in memory; foreground is any non-zero pixel. The
implementations are based on the OpenCV tutorials *Contour Features* and
*Contour Properties*; both languages expose the same functions and produce the
same results.

### Files

- **contour_measure.py** - embeddable Python module (OpenCV, NumPy); one
  function per measured property. No file I/O, no CLI.
- **contour_measure.cpp** - embeddable C++ source (OpenCV C++ API) with the
  same functions in the `contour` namespace. No file I/O and no `main()`:
  compile it together with the calling code or `#include` it.

### API

Contours are obtained with `find_contours`; every property is measured by its
own function. All contour-based functions take a single non-empty contour;
intensity functions take the binary image in addition. In C++ the functions
live in `namespace contour`.

| Function (Python / C++) | Returns |
|---|---|
| `find_contours(binary)` | list of contours (outer contours of all non-zero regions, `RETR_EXTERNAL` + `CHAIN_APPROX_SIMPLE`) |
| `moments(contour)` | spatial, central and normalized moments up to order 3 |
| `centroid(contour)` | center of mass `(x, y)` |
| `area(contour)` / `perimeter(contour)` | polygon area / closed arc length |
| `approx_epsilon(contour)` | Douglas-Peucker epsilon (1% of the arc length) |
| `approx_poly(contour)` | vertices of the approximated polygon |
| `convex_hull(contour)` / `hull_area(contour)` | hull vertices / hull area |
| `is_convex(contour)` | whether the contour is convex |
| `solidity(contour)` / `solidity_from(area, hull_area)` | contour area divided by hull area |
| `bounding_rect(contour)` | up-right bounding rectangle |
| `aspect_ratio(contour)` / `aspect_ratio_from(rect)` | width / height of the bounding rectangle |
| `extent(contour)` / `extent_from(area, rect)` | contour area divided by rectangle area |
| `min_area_rect(contour)` | rotated rectangle of minimum area (center, size, angle) |
| `min_enclosing_circle(contour)` | minimum area circle (center, radius) |
| `fit_ellipse(contour)` | fitted ellipse (center, axes, angle) |
| `fit_line(contour)` | fitted line (direction `(vx, vy)` + support point) |
| `line_angle_deg(vx, vy)` | direction angle of a fitted line in degrees |
| `equivalent_diameter(contour)` / `equivalent_diameter_from(area)` | diameter of the circle with the area |
| `extreme_points(contour)` | topmost, bottommost, leftmost and rightmost points |
| `mask(binary, contour)` | filled binary mask of the contour region |
| `pixel_count(binary, contour)` | number of pixels inside the contour |
| `mean_intensity(binary, contour)` | mean intensity within the contour mask |
| `min_max_intensity(binary, contour)` | min/max intensity and their locations within the contour mask |

The `*_from` variants are pure derived measures taking already computed
inputs; both forms give identical results.

### Embedding

Python:

```python
import numpy as np
from contour_measure import find_contours, area, solidity, equivalent_diameter

binary: np.ndarray  # uint8, single channel

for c in find_contours(binary):
    print(area(c), solidity(c), equivalent_diameter(c))
```

C++ (compile this file together with your code, or `#include` it):

```cpp
#include <opencv2/core.hpp>
#include "contour_measure.cpp"

cv::Mat binary;  // CV_8UC1 binary image

for (const std::vector<cv::Point>& c : contour::find_contours(binary)) {
    std::printf("%g %g %g\n", contour::area(c), contour::solidity(c),
                contour::equivalent_diameter(c));
}
```

### Notes

- Because the input is binary, the intensity properties are evaluated within a
  filled mask of each contour and collapse to the foreground value (typically
  `255`); they are kept for API completeness.
- A numeric value is `NaN` (Python `float('nan')` / C++ quiet NaN) when the
  measure is not computable, e.g. the ellipse fit for a contour with fewer
  than 5 points or the line fit with fewer than 2 points.
- An empty contour throws `ValueError` / `std::invalid_argument`; an image with
  no non-zero pixels yields an empty contour list.
- Input validation: a non-`uint8`/non-`CV_8UC1` image raises `ValueError` /
  `std::invalid_argument`.
- `contourArea` measures the polygon spanned by the contour points; for filled
  regions this is smaller than the pixel count (e.g. a `60 x 30` rectangle
  gives 1711 instead of 1800).

### References

- [OpenCV: Contour Features](https://docs.opencv.org/3.4.20/dd/d49/tutorial_py_contour_features.html)
- [OpenCV: Contour Properties](https://docs.opencv.org/3.4.20/d1/d32/tutorial_py_contour_properties.html)

## Noise measurement

The noise measurement library estimates pixel-wise sensor noise (modelled as
approximately additive zero-mean Gaussian) in an NV12 color frame, as output
by the Arducam camera. The estimators return the noise standard deviation
`sigma` in gray levels; `noise_index()` normalizes it to a "noise present"
scalar. Noise is measured on the Y (luma) plane by default; the U and V
planes are extracted separately for an optional chroma check.

### Files

- **noise_measure.py** - embeddable Python module (OpenCV, NumPy); one
  function per property. No file I/O, no CLI.
- **noise_measure.cpp** - embeddable C++ source (OpenCV C++ API) with the
  same functions in the `noise` namespace. No file I/O and no `main()`:
  compile it together with the calling code or `#include` it.

### API

An NV12 frame is `width * height * 3 / 2` bytes: the full-resolution Y plane
first, then the interleaved U,V 4:2:0 chroma block. Every estimator performs
a single high-pass convolution only - no patch search, no PCA, no machine
learning.

| Function (Python / C++) | Returns |
|---|---|
| `y_plane(buffer, w, h)` | Y plane as an `(h, w)` 8-bit image (zero-copy view) |
| `uv_planes(buffer, w, h)` | deinterleaved U and V planes, each `(h/2, w/2)` |
| `immerkaer_sigma(plane)` | Gaussian noise `sigma` in gray levels (Immerkær 1996) |
| `mad_sigma(plane)` | robust `sigma` (median of the same high-pass response) |
| `noise_index(sigma)` | normalized presence measure `sigma / 255`, roughly 0..1 |

In C++ the frame is passed as `(const uint8_t* buffer, int width, int height)`
and the functions live in `namespace noise`.

### Embedding

Python:

```python
import numpy as np
from noise_measure import y_plane, immerkaer_sigma, noise_index

nv12: np.ndarray  # uint8, size w*h*3//2, e.g. one Arducam frame
w, h = 1920, 1080

sigma = immerkaer_sigma(y_plane(nv12, w, h))
print(sigma, noise_index(sigma))
```

C++ (compile together or `#include`):

```cpp
#include <opencv2/core.hpp>
#include "noise_measure.cpp"

const uint8_t* nv12;  // w*h*3/2 bytes, e.g. one Arducam frame
int w = 1920, h = 1080;

double sigma = noise::immerkaer_sigma(noise::y_plane(nv12, w, h));
std::printf("%g %g\n", sigma, noise::noise_index(sigma));
```

### Notes

- `mad_sigma()` is the robust counterpart to `immerkaer_sigma()`; use it as a
  counter-check on strongly textured scenes. Immerkær tends to underestimate
  very weak noise and to overestimate on strong structure.
- NV12 Y is gamma-corrected and already processed in-camera, so the result is
  a perceived gray-level noise strength, not the true photon-shot-noise sigma.
- A perfectly flat plane yields (close to) `0`; sigma is always `>= 0`.
- Input validation: wrong buffer size, dimensions smaller than `3x3` or a
  non-`uint8` plane raise `ValueError` / `std::invalid_argument`. In C++ the
  frame size itself cannot be verified behind a raw pointer and is the
  caller's contract.

### References

- [J. Immerkær: Fast Noise Variance Estimation, Computer Vision and Image Understanding 64(2):300-302, 1996](https://doi.org/10.1006/cviu.1996.0060)