import time
from machine import Pin

import hc595_rgb

latch = Pin(17, Pin.OUT, value=0)
panel = hc595_rgb.HC595RGB(Pin(19), Pin(18), latch)

print("demo.py started — 8x8 RGB matrix via 4x 74HC595")

COLORS = (
    ((255, 0, 0), "red"),
    ((0, 255, 0), "green"),
    ((0, 0, 255), "blue"),
    ((255, 255, 0), "yellow"),
    ((0, 255, 255), "cyan"),
    ((255, 0, 255), "magenta"),
    ((255, 255, 255), "white"),
    ((0, 0, 0), "off"),
)


def run():
    phase = 0
    step = 0
    next_change = time.ticks_ms()

    def hook():
        nonlocal phase, step, next_change
        now = time.ticks_ms()
        if time.ticks_diff(now, next_change) < 0:
            return
        if phase == 0:
            brightness = (5, 25, 50, 75, 100)[step]
            panel.fill(255, 255, 255)
            panel.brightness(brightness)
            print("brightness %d%%" % brightness)
            step += 1
            if step >= 5:
                phase = 1
                step = 0
            next_change = now + 10000
        else:
            rgb, name = COLORS[step]
            panel.fill(*rgb)
            panel.brightness(100)
            print(name)
            step += 1
            if step >= len(COLORS):
                step = 0
            next_change = now + 10000

    panel.scan_loop(hook_ms=50, hook=hook)


run()
