import time
from machine import Pin

import hc595_rgb

latch = Pin(17, Pin.OUT, value=0)
panel = hc595_rgb.HC595RGB(Pin(19), Pin(18), latch)

BLUE1_DIM = (0x00, 0x31, 0x56)
BRIGHTNESS = 50

panel.brightness(BRIGHTNESS)
panel.fill(*BLUE1_DIM)
panel.scan_loop(hook_ms=50)
