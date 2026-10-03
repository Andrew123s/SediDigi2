#!/usr/bin/env python3
"""Cycle a broad range of blue shades on the RGB matrix at 50 % brightness.

Sends a sequence of SET commands to the Pico panel server, holding each
shade for HOLD_SECONDS, until the user presses Enter. Then sends OFF to
turn the matrix off and exits.

Usage:
    python3 blue_dyn.py
"""

import select
import sys
import time

from pico_link import PicoLink

BRIGHTNESS = 50
HOLD_SECONDS = 5
STEPS = 16


def blue_shades():
    """Dark blue -> cyan-blue, then violet -> magenta (red enters in phase 2)."""
    for i in range(STEPS):
        if i < STEPS // 2:
            t = i / (STEPS // 2 - 1)
            r, g, b = 0x00, int(0x40 * t), int(0x20 + 0xDF * t)
        else:
            t = (i - STEPS // 2) / (STEPS // 2 - 1)
            r, g, b = int(0xFF * t), int(0x40 * (1 - t)), 0xFF
        yield f"{r:02x}{g:02x}{b:02x}"


def main():
    with PicoLink() as link:
        print("PING ->", link.ping())
        print("Press Enter to stop and turn the panel off.")
        for hex_color in blue_shades():
            print(f"SET {hex_color} {BRIGHTNESS} ->",
                  link.set_color(hex_color, BRIGHTNESS))
            if select.select([sys.stdin], [], [], HOLD_SECONDS)[0]:
                sys.stdin.readline()
                break
        print("OFF ->", link.off())


if __name__ == "__main__":
    main()
