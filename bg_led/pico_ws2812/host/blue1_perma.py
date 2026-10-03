#!/usr/bin/env python3
"""Hold the RGB matrix on "Blue tone 1" at 50 % brightness, then turn it off.

Sends a SET to the Pico panel server and keeps the panel on until the user
presses Enter, then sends OFF to turn the matrix off and exits.

Usage:
    python3 blue1_perma.py
"""

from pico_link import PicoLink

BLUE1 = "003156"
BRIGHTNESS = 60


def main():
    with PicoLink() as link:
        print("PING ->", link.ping())
        print("SET %s %d ->" % (BLUE1, BRIGHTNESS),
              link.set_color(BLUE1, BRIGHTNESS))
        try:
            input("Press Enter to turn the panel off and exit ...\n")
        except EOFError:
            pass
        print("OFF ->", link.off())


if __name__ == "__main__":
    main()
