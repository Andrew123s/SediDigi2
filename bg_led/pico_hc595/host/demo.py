#!/usr/bin/env python3
"""Communication demo: PING, color/brightness steps, OFF.

The panel is an 8x8 RGB matrix ("LED Matrix 1.0", 4x 74HC595) driven by a
Pico 2 (W); the color value is applied as-is.

Each state is held for 10 seconds so the panel can be visually checked.
"""

import time

from pico_link import PicoLink


def main():
    with PicoLink() as link:
        print("PING ->", link.ping())
        print("SET 0062ac 40 ->", link.set_color("0062ac", 40))
        time.sleep(10)
        print("SET 0062ac 25 ->", link.set_color("0062ac", 25))
        time.sleep(10)
        print("SET ff0000 30 ->", link.set_color("ff0000", 30))
        time.sleep(10)
        print("OFF ->", link.off())
    print("Demo finished.")


if __name__ == "__main__":
    main()
