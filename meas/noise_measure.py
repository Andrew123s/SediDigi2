"""Measure pixel-wise sensor noise in an NV12 color frame.

Embeddable library (no file I/O, no CLI): pass a raw NV12 frame
(Arducam-style, 8-bit) with its width and height, extract the Y (luma) plane
or deinterleave the U and V planes, and estimate the noise level of any of
them.

NV12 layout (``width * height * 3 / 2`` bytes):

    Y plane: width*height bytes, row-major, full resolution.
    UV plane: width*height/2 bytes, interleaved U,V,U,V,... 4:2:0 chroma.

The noise is modelled as approximately additive zero-mean Gaussian ("sensor
noise"): the estimators return its standard deviation sigma in gray levels.
`noise_index()` normalizes sigma to a 0..1 "presence" scalar.

Conventions:
    * ``buffer`` is a contiguous uint8 array of size ``width * height * 3 // 2``.
    * ``width`` and ``height`` must be at least 3.
    * A plane is a single-channel uint8 image; sigma functions take such a
      plane (usually ``y_plane(...)`` or one of ``uv_planes(...)``).
    * Sigma is always >= 0; a perfectly flat plane yields (close to) 0.
    * No NaN cases: an input error raises ValueError / TypeError instead.

Heuristic caveat: NV12 Y is gamma-corrected and already filtered in-camera,
so this estimates a perceived gray-level noise strength, not the true
photon-shot-noise sigma. `mad_sigma()` is the robust counterpart to
`immerkaer_sigma()` (less biased by image texture); Immerkær tends to
underestimate for very weak noise and to overestimate on strong structure.

Based on J. Immerkaer, "Fast Noise Variance Estimation", Computer Vision and
Image Understanding, vol. 64, no. 2, pp. 300-302, 1996:

    https://doi.org/10.1006/cviu.1996.0060

Dependencies:
    python3 -m pip install opencv-python numpy
"""

import math

import cv2
import numpy as np

SQRT_PI_OVER_2 = math.sqrt(math.pi / 2.0)  # Immerkaer scaling factor sqrt(pi/2)
MAD_SCALE = 1.4826  # MAD -> sigma for a Gaussian distribution
EDGE = 1  # fully valid interior after the 3x3 high-pass convolution
HIGHPASS_KERNEL = np.array(
    [[1, -2, 1], [-2, 4, -2], [1, -2, 1]], dtype=np.float64
)  # Immerkaer high-pass mask F


def _validate_nv12(buffer, width, height):
    """Check that ``buffer`` is a contiguous uint8 NV12 frame of the given size."""
    if not isinstance(buffer, np.ndarray) or buffer.dtype != np.uint8:
        raise TypeError("buffer must be a numpy uint8 array")
    if width < 3 or height < 3:
        raise ValueError("width and height must be at least 3")
    expected = width * height * 3 // 2
    if buffer.size != expected:
        raise ValueError(
            f"NV12 buffer must have {expected} bytes for {width}x{height}; "
            f"got {buffer.size}"
        )


def _validate_plane(plane):
    """Check that ``plane`` is a single-channel uint8 image of at least 3x3."""
    if not isinstance(plane, np.ndarray):
        raise TypeError("plane must be a numpy.ndarray")
    if plane.ndim != 2 or plane.dtype != np.uint8:
        raise ValueError("plane must be a single-channel uint8 image")
    if plane.shape[0] < 3 or plane.shape[1] < 3:
        raise ValueError("plane must be at least 3x3 pixels")


def _highpass_abs(plane):
    """Return |I * F| on the fully valid interior of the Immerkaer mask."""
    _validate_plane(plane)
    response = cv2.filter2D(
        plane.astype(np.float64), cv2.CV_64F, HIGHPASS_KERNEL,
        borderType=cv2.BORDER_REPLICATE,
    )
    return np.abs(response[EDGE:-EDGE, EDGE:-EDGE])


# --- NV12 plane extraction ---------------------------------------------------

def y_plane(buffer, width, height):
    """Return the Y (luma) plane of an NV12 frame as a (height, width) view
    of the original buffer (zero copy).
    """
    _validate_nv12(buffer, width, height)
    return buffer[: width * height].reshape(height, width)


def uv_planes(buffer, width, height):
    """Return the (U, V) planes of an NV12 frame as separate
    (height/2, width/2) uint8 arrays (deinterleaved 4:2:0 chroma).
    """
    _validate_nv12(buffer, width, height)
    chroma = buffer[width * height :].reshape(height // 2, width // 2, 2)
    return chroma[:, :, 0].copy(), chroma[:, :, 1].copy()


# --- Noise estimators --------------------------------------------------------

def immerkaer_sigma(plane):
    """Return an estimate of the Gaussian noise sigma in gray levels:
    one high-pass convolution, |r| summed over the valid interior and scaled
    by sqrt(pi/2) / (6 * (W-2) * (H-2)) (Immerkaer 1996).
    """
    response = _highpass_abs(plane)
    height, width = response.shape
    return SQRT_PI_OVER_2 * float(np.sum(response)) / (6.0 * width * height)


def mad_sigma(plane):
    """Return a robust estimate of the Gaussian noise sigma in gray levels:
    the median of |r| on the valid interior, scaled by 1.4826 / 6. Shares its
    single convolution with immerkaer_sigma; less biased by image texture.
    """
    response = _highpass_abs(plane)
    median = float(np.median(response))
    return MAD_SCALE / 6.0 * median


def noise_index(sigma):
    """Return the normalized noise presence: sigma / 255, i.e. roughly 0..1
    of the full gray-level range.
    """
    return sigma / 255.0