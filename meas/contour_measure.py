"""Measure contour properties of a binary image.

Embeddable library (no file I/O, no CLI): take a binary image -- an 8-bit,
single-channel numpy array --, find its contours with find_contours() and
measure any property with a dedicated function.

Conventions:
    * A contour is a non-empty int32 ``(N, 1, 2)`` array as returned by
      find_contours(); passing an empty contour raises ValueError.
    * A numeric value that cannot be computed (e.g. the ellipse fit for fewer
      than 5 points) is NaN.
    * Derived ratios (solidity, aspect ratio, extent, equivalent diameter)
      exist both as contour functions and as ``*_from`` helpers that take the
      already measured inputs.
    * Intensity functions take the binary image in addition to the contour.

Based on the OpenCV tutorials "Contour Features" and "Contour Properties":

    https://docs.opencv.org/3.4.20/dd/d49/tutorial_py_contour_features.html
    https://docs.opencv.org/3.4.20/d1/d32/tutorial_py_contour_properties.html

Dependencies:
    python3 -m pip install opencv-python numpy
"""

import math

import cv2
import numpy as np

APPROX_EPSILON = 0.01  # Douglas-Peucker epsilon as a fraction of the arc length


def _validate_binary(binary):
    """Check that ``binary`` is a single-channel uint8 image."""
    if not isinstance(binary, np.ndarray):
        raise TypeError("binary must be a numpy.ndarray")
    if binary.ndim != 2:
        raise ValueError("binary must be a single-channel image")
    if binary.dtype != np.uint8:
        raise ValueError("binary must have dtype uint8")


def _require_contour(contour):
    """Check that ``contour`` is a non-empty numpy array."""
    if not isinstance(contour, np.ndarray) or len(contour) == 0:
        raise ValueError("contour must be a non-empty contour array")


def find_contours(binary):
    """Return the outer contours of all non-zero regions (RETR_EXTERNAL,
    CHAIN_APPROX_SIMPLE); compatible with OpenCV 3.x and 4.x.
    """
    _validate_binary(binary)
    result = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if len(result) == 3:
        _, contours, _ = result
    else:
        contours, _ = result
    return contours


# --- Moments and centroid ---------------------------------------------------

def moments(contour):
    """Return the image moments of a contour (m00..m01, mu20..mu11, nu20..nu11)."""
    _require_contour(contour)
    m = cv2.moments(contour)
    keys = ("m00", "m10", "m01", "mu20", "mu02", "mu11", "nu20", "nu02", "nu11")
    return {k: m[k] for k in keys}


def centroid(contour):
    """Return the centroid (center of mass) of a contour; (nan, nan) if the
    area m00 is zero.
    """
    _require_contour(contour)
    m = cv2.moments(contour)
    if m["m00"]:
        return (m["m10"] / m["m00"], m["m01"] / m["m00"])
    nan = float("nan")
    return (nan, nan)


# --- Basic shape ------------------------------------------------------------

def area(contour):
    """Return the polygon area of a contour (cv2.contourArea, absolute value)."""
    _require_contour(contour)
    return abs(cv2.contourArea(contour))


def perimeter(contour):
    """Return the perimeter (arc length) of the closed contour."""
    _require_contour(contour)
    return cv2.arcLength(contour, True)


# --- Approximation -----------------------------------------------------------

def approx_epsilon(contour):
    """Return the Douglas-Peucker epsilon: APPROX_EPSILON times the perimeter."""
    _require_contour(contour)
    return APPROX_EPSILON * cv2.arcLength(contour, True)


def approx_poly(contour):
    """Return the Douglas-Peucker approximation of the contour as (x, y) tuples."""
    _require_contour(contour)
    approx = cv2.approxPolyDP(contour, approx_epsilon(contour), True)
    return [(int(p[0][0]), int(p[0][1])) for p in approx]


# --- Convexity ---------------------------------------------------------------

def convex_hull(contour):
    """Return the convex hull of the contour as (x, y) tuples."""
    _require_contour(contour)
    hull = cv2.convexHull(contour)
    return [(int(p[0][0]), int(p[0][1])) for p in hull]


def hull_area(contour):
    """Return the polygon area of the convex hull (absolute value)."""
    _require_contour(contour)
    return abs(cv2.contourArea(cv2.convexHull(contour)))


def is_convex(contour):
    """Return whether the contour is convex."""
    _require_contour(contour)
    return bool(cv2.isContourConvex(contour))


def solidity_from(area_value, hull_area_value):
    """Derived: area / hull area; NaN if the hull area is zero."""
    return area_value / hull_area_value if hull_area_value > 0 else float("nan")


def solidity(contour):
    """Return the solidity (area / convex hull area); NaN if the hull area is
    zero.
    """
    _require_contour(contour)
    return solidity_from(area(contour), hull_area(contour))


# --- Bounding rectangle ------------------------------------------------------

def bounding_rect(contour):
    """Return the up-right bounding rectangle as (x, y, width, height)."""
    _require_contour(contour)
    x, y, w, h = cv2.boundingRect(contour)
    return (int(x), int(y), int(w), int(h))


def aspect_ratio_from(rect):
    """Derived: width / height of a bounding rectangle; NaN if the height is
    zero.
    """
    if rect[3] > 0:
        return rect[2] / rect[3]
    return float("nan")


def aspect_ratio(contour):
    """Return the bounding-rectangle aspect ratio (width / height); NaN for a
    zero height.
    """
    _require_contour(contour)
    return aspect_ratio_from(bounding_rect(contour))


def extent_from(area_value, rect):
    """Derived: area / (rect width * rect height); NaN if a rect side is zero."""
    width, height = rect[2], rect[3]
    if width > 0 and height > 0:
        return area_value / (width * height)
    return float("nan")


def extent(contour):
    """Return the extent (area / bounding rectangle area); NaN if a rect side
    is zero.
    """
    _require_contour(contour)
    return extent_from(area(contour), bounding_rect(contour))


# --- Rotated rectangle -------------------------------------------------------

def min_area_rect(contour):
    """Return the minimum-area rotated rectangle as (center, size, angle);
    NaN values for fewer than 2 points.
    """
    _require_contour(contour)
    nan = float("nan")
    if len(contour) < 2:
        return ((nan, nan), (nan, nan), nan)
    (cx, cy), (w, h), angle = cv2.minAreaRect(contour)
    return ((float(cx), float(cy)), (float(w), float(h)), float(angle))


# --- Enclosing circle --------------------------------------------------------

def min_enclosing_circle(contour):
    """Return the minimum enclosing circle as (center, radius); NaN values for
    fewer than 2 points.
    """
    _require_contour(contour)
    nan = float("nan")
    if len(contour) < 2:
        return ((nan, nan), nan)
    (cx, cy), radius = cv2.minEnclosingCircle(contour)
    return ((float(cx), float(cy)), float(radius))


# --- Ellipse and line fitting ------------------------------------------------

def fit_ellipse(contour):
    """Fit an ellipse to the contour (center, axes, angle); NaN values for
    fewer than 5 points.
    """
    _require_contour(contour)
    nan = float("nan")
    if len(contour) < 5:
        return ((nan, nan), (nan, nan), nan)
    (cx, cy), (major, minor), angle = cv2.fitEllipse(contour)
    return ((float(cx), float(cy)), (float(major), float(minor)), float(angle))


def fit_line(contour):
    """Fit a line to the contour (vx, vy, px, py); NaN values for fewer than 2
    points.
    """
    _require_contour(contour)
    nan = float("nan")
    if len(contour) < 2:
        return (nan, nan, nan, nan)
    vx, vy, px, py = cv2.fitLine(contour, cv2.DIST_L2, 0, 0.01, 0.01).flatten()
    return (float(vx), float(vy), float(px), float(py))


def line_angle_deg(vx, vy):
    """Return the direction angle of a fitted line in degrees (atan2(vy, vx))."""
    return math.degrees(math.atan2(vy, vx))


# --- Derived measures --------------------------------------------------------

def equivalent_diameter_from(area_value):
    """Derived: diameter of a circle with the given area; 0 if the area is
    zero.
    """
    if area_value > 0:
        return math.sqrt(4 * area_value / math.pi)
    return 0.0


def equivalent_diameter(contour):
    """Return the equivalent diameter of the contour (sqrt(4 * area / pi)); 0
    if the area is zero.
    """
    _require_contour(contour)
    return equivalent_diameter_from(area(contour))


# --- Extreme points ----------------------------------------------------------

def extreme_points(contour):
    """Return the extreme points (top, bottom, left, right) of the contour."""
    _require_contour(contour)
    pts = contour.reshape(-1, 2)
    xs = pts[:, 0]
    ys = pts[:, 1]
    left = (int(xs.min()), int(ys[xs.argmin()]))
    right = (int(xs.max()), int(ys[xs.argmax()]))
    top = (int(xs[ys.argmin()]), int(ys.min()))
    bottom = (int(xs[ys.argmax()]), int(ys.max()))
    return (top, bottom, left, right)


# --- Intensity (requires the binary image) -----------------------------------

def mask(binary, contour):
    """Return a filled uint8 mask of the contour region (same size as binary)."""
    _validate_binary(binary)
    _require_contour(contour)
    result = np.zeros(binary.shape, dtype=np.uint8)
    cv2.drawContours(result, [contour], -1, 255, -1)
    return result


def pixel_count(binary, contour):
    """Return the number of pixels inside the contour (filled mask)."""
    _validate_binary(binary)
    _require_contour(contour)
    msk = cv2.drawContours(
        np.zeros(binary.shape, dtype=np.uint8), [contour], -1, 255, -1
    )
    return int(cv2.countNonZero(msk))


def mean_intensity(binary, contour):
    """Return the mean intensity of binary within the contour mask; the
    foreground value for a binary input.
    """
    _validate_binary(binary)
    _require_contour(contour)
    msk = cv2.drawContours(
        np.zeros(binary.shape, dtype=np.uint8), [contour], -1, 255, -1
    )
    return float(cv2.mean(binary, mask=msk)[0])


def min_max_intensity(binary, contour):
    """Return (min, max, min_loc, max_loc) intensities within the contour
    mask; NaN values and (nan, nan) locations if no pixels are masked.
    """
    _validate_binary(binary)
    _require_contour(contour)
    msk = cv2.drawContours(
        np.zeros(binary.shape, dtype=np.uint8), [contour], -1, 255, -1
    )
    nan = float("nan")
    if cv2.countNonZero(msk) == 0:
        return (nan, nan, (nan, nan), (nan, nan))
    mn, mx, mn_loc, mx_loc = cv2.minMaxLoc(binary, mask=msk)
    return (
        float(mn),
        float(mx),
        (int(mn_loc[0]), int(mn_loc[1])),
        (int(mx_loc[0]), int(mx_loc[1])),
    )