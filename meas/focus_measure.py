#!/usr/bin/env python3
"""Measure the sharpness of a digital image using the Tenengrad focus measure.

For a single input image file the script prints one scalar score. Higher
values indicate a sharper image.

Tenengrad focus measure:

    F = (1 / N) * sum(Ix^2 + Iy^2)

with Ix, Iy being the Sobel gradient components of the grayscale image and
N the number of pixels used. The score is thus normalized by pixel count and
comparable across different resolutions and crops.

Dependencies:
    python3 -m pip install opencv-python numpy
"""

import argparse
import json
import sys

import cv2
import numpy as np


def tenengrad(gray: np.ndarray) -> float:
    """Return the Tenengrad focus measure of a grayscale image."""
    sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    energy = sobel_x * sobel_x + sobel_y * sobel_y
    return float(np.mean(energy))


def center_crop(gray: np.ndarray, fraction: float) -> np.ndarray:
    """Return a centered square crop covering `fraction` of the smaller side."""
    if not 0.0 < fraction <= 1.0:
        raise ValueError("--roi-fraction must be in the range (0, 1]")
    h, w = gray.shape
    side = int(round(fraction * min(h, w)))
    x0 = (w - side) // 2
    y0 = (h - side) // 2
    return gray[y0:y0 + side, x0:x0 + side]


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description=(
            "Compute the Tenengrad sharpness score of an image. "
            "One score per image; higher is sharper."
        ),
    )
    parser.add_argument("image", help="Path to the input image file")
    parser.add_argument(
        "--scale",
        type=float,
        default=1.0,
        metavar="F",
        help="Downscale factor applied before measuring "
        "(e.g. 0.5 halves each dimension, default: 1.0)",
    )
    parser.add_argument(
        "--roi",
        choices=("full", "center"),
        default="full",
        help="Region of interest: the whole image or a centered crop "
        "(default: full)",
    )
    parser.add_argument(
        "--roi-fraction",
        type=float,
        default=0.8,
        metavar="F",
        help="Side length of the center crop as a fraction of the smaller "
        "image side (used with --roi center, default: 0.8)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the score as a single JSON object",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    gray = cv2.imread(args.image, cv2.IMREAD_GRAYSCALE)
    if gray is None:
        sys.exit(f"error: could not read image: {args.image}")

    if args.scale <= 0.0 or args.scale > 1.0:
        sys.exit("error: --scale must be in the range (0, 1]")

    if args.scale != 1.0:
        new_width = max(1, int(round(gray.shape[1] * args.scale)))
        new_height = max(1, int(round(gray.shape[0] * args.scale)))
        gray = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_AREA)

    if args.roi == "center":
        gray = center_crop(gray, args.roi_fraction)

    score = tenengrad(gray)

    if args.json:
        print(json.dumps(
            {
                "image": args.image,
                "score": score,
                "width": gray.shape[1],
                "height": gray.shape[0],
                "region": args.roi,
                "scale": args.scale,
            },
            indent=2,
        ))
    else:
        print(f"{score:.6f}")


if __name__ == "__main__":
    main()
