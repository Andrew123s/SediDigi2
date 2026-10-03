import rp2
import time
import gc
from machine import Pin, disable_irq, enable_irq

NUM_LEDS = 25          # 25 for 5×5 panel, 64 for 8×8 panel

@rp2.asm_pio(
    sideset_init=rp2.PIO.OUT_LOW,
    out_shiftdir=rp2.PIO.SHIFT_LEFT,
    autopull=True,
    pull_thresh=24,
)
def ws2812():
    T1 = 3
    T2 = 3
    T3 = 4
    wrap_target()
    label("bitloop")
    out(x, 1)               .side(0) [T3 - 1]
    jmp(not_x, "do_zero")   .side(1) [T1 - 1]
    jmp("bitloop")          .side(1) [T2 - 1]
    label("do_zero")
    nop()                   .side(0) [T2 - 1]
    wrap()


sm = rp2.StateMachine(0, ws2812, freq=8_000_000, sideset_base=Pin(0))
sm.active(1)


def grb_24(r, g, b):
    return ((g << 24) | (r << 16) | (b << 8)) & 0xFFFFFF00


def show(colors):
    irq_state = disable_irq()
    gc.disable()
    for i in range(NUM_LEDS):
        sm.put(grb_24(*colors[i % len(colors)]))
    while sm.tx_fifo() > 0:
        pass
    time.sleep_us(50)
    sm.active(0)
    gc.enable()
    enable_irq(irq_state)
    time.sleep_us(300)
    gc.disable()
    sm.active(1)
    gc.enable()


blue_tones = [
    (0x00, 0x62, 0xac),  # Blue 1
    (0x17, 0x38, 0x8c),  # Blue 2
    (0x00, 0x83, 0xc9),  # Blue 3
    (0x00, 0x79, 0xba),  # Blue 4
    (0x00, 0x63, 0xac),  # Blue 5
    (0x00, 0x6b, 0xb5),  # Blue 6
    (0x00, 0x59, 0x9f),  # Blue 7
]

SCHEME_RED = [(0xFF, 0x00, 0x00)]
SCHEME_GREEN = [(0x00, 0xFF, 0x00)]
SCHEME_BLUE = [(0x00, 0x00, 0xFF)]
SCHEME_WHITE = [(0xFF, 0xFF, 0xFF)]

print(f"demo.py started — {NUM_LEDS} LED WS2812 via PIO")

while True:
    print("1) Red")
    show(SCHEME_RED)
    time.sleep(5)

    print("2) Green")
    show(SCHEME_GREEN)
    time.sleep(5)

    print("3) Blue")
    show(SCHEME_BLUE)
    time.sleep(5)

    for i, (r, g, b) in enumerate(blue_tones, 1):
        print(f"4.{i}) Blue tone #{r:02x}{g:02x}{b:02x}")
        show([(r, g, b)])
        time.sleep(5)

    for br in (0.25, 0.50, 1.00):
        print(f"5) White @ {br:.0%} brightness")
        v = int(0xFF * br)
        show([(v, v, v)])
        time.sleep(5)

    print("--- restart ---")
