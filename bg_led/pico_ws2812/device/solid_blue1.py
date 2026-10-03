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

BLUE1_DIM = [(0x00, 0x31, 0x56)]
show(BLUE1_DIM)
time.sleep(9999)
