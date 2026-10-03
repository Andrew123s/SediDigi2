"""Driver for an 8x8 RGB LED matrix ("LED Matrix 1.0", 4x 74HC595 shift registers for row and color drive).

Reference implementation (Arduino, timer ISR + bit-plane PWM):
    madworm/V3_x_boards_test  -- https://github.com/madworm/V3_x_boards_test

Calibrated against the actual panel ("LED Matrix 1.0", 4x 74HC595): the
32-bit frame is [red(8), blue(8), green(8), row(8)] with active-low color
bits and a one-hot active-high row byte. This differs from the madworm
reference, which is [row, blue, green, red] with active-low colors; the row
register sits in the last slot here.

The single active row line cannot source all 24 color columns at once (red's
lower forward voltage wins, green/blue collapse). Colors are therefore
time-sliced: each (bit plane, row) emits three separate frames, one per
channel, so at most 8 columns are on per frame. Mixed colors are produced
temporally and are blended by the eye/camera.

Refresh is driven entirely by hardware: a PIO state machine shifts each
frame out on MOSI/SCK and pulses the STCP latch, while DMA channel 0 feeds
the precomputed frame buffer into the PIO TX FIFO. When channel 0 finishes
the buffer it chains to channel 1 (CHAIN_TO); channel 1 is a one-word
transfer that writes the buffer address into channel 0's AL3_READ_ADDR_TRIG
register (offset 0x3C), reloading channel 0's transfer count from its shadow
and re-launching the read at the buffer base. Channel 1 does not increment
its read or write address, so the same slot is read and the same trigger
written on every pass. This produces an endless refresh loop without any
Python involvement; the cadence is set by PIO_FREQ and is independent of the
interpreter.

This driver targets the RP2350 (Pico 2 / Pico 2 W). The DMA register
layout differs from the RP2040: CHAN_ABORT lives at 0x464 (not 0x444),
CTRL_TRIG bit positions are shifted (INCR_WRITE=6, RING=8-12, CHAIN_TO=13-16,
TREQ_SEL=17-22, BUSY=26), and TRANS_COUNT gained a MODE field (bits 28-31).
RP2350 TRANS_COUNT_MODE=TRIGGER_SELF is deliberately not used: it reloads
only the transfer count, not the addresses, so an 8-word ring (RING_SIZE=3)
would be needed to wrap the read pointer, which requires the buffer base to
be 32-byte aligned and is not guaranteed for a GC array. ch1's
non-incrementing one-word kick resets the read pointer each pass and
keeps the frame count at a clean 360.

    ROW_ACTIVE       row select polarity (1 = one-hot active high)
    COLOR_ACTIVE     color bit polarity (0 = active low, bit clear = LED on)
    CHANNEL_ORDER    order of the three color bytes inside the 32-bit frame
    COLOR_BITS       color depth in bits per channel (drives PWM passes)
    PIO_FREQ         PIO clock; refresh ~= PIO_FREQ / (4 * 32 * frames)
    CROP_COLS        columns that are never lit, counted from the connector
                     end (0 = drive all columns); the row scan and the frame
                     count stay unchanged
    CROP_COLS_FROM_HIGH   crop columns x = _N_COLS-CROP_COLS .. _N_COLS-1
                          (True) instead of x = 0 .. CROP_COLS-1 (False)

Brightness 0..100 is applied as a global scale factor on the stored RGB
values before quantization to COLOR_BITS bits.
"""

import time
from array import array

from machine import Pin

ROW_ACTIVE = 1
COLOR_ACTIVE = 0
CHANNEL_ORDER = ("r", "b", "g")
COLOR_BITS = 4
PIO_FREQ = 64_000_000
CROP_COLS = 3
CROP_COLS_FROM_HIGH = True

_N_COLS = 8
_N_ROWS = 8
_CHANNELS = ("r", "g", "b")
_CHANNEL_INDEX = {"r": 0, "g": 1, "b": 2}

_DMA_BASE = 0x50000000
_PIO0_TXF0 = 0x50200010
_DMA_CHAN_ABORT = _DMA_BASE + 0x464
_DMA_CTRL_CH0 = (1 << 0) | (2 << 2) | (1 << 4) | (1 << 13)
_DMA_CTRL_CH1 = (1 << 0) | (2 << 2) | (0x3F << 17)


class HC595RGB:
    def __init__(self, mosi, sck, latch):
        self._mosi = mosi
        self._sck = sck
        self._latch = latch
        self._fb = [[(0, 0, 0) for _ in range(_N_COLS)] for _ in range(_N_ROWS)]
        self._brightness = 100
        self._dirty = True
        self._frames = []
        self._dma_buf = None
        self._kick = None
        self._sm = None
        self._rebuild()
        self._dma_buf = array("I", [0] * len(self._frames))
        self._pack_buffer()

    def set_pixel(self, x, y, r, g, b):
        if 0 <= x < _N_COLS and 0 <= y < _N_ROWS:
            self._fb[x][y] = (r, g, b)
            self._dirty = True

    def fill(self, r, g, b):
        for x in range(_N_COLS):
            self._fb[x] = [(r, g, b)] * _N_ROWS
        self._dirty = True

    def brightness(self, value):
        self._brightness = max(0, min(100, value))
        self._dirty = True

    def _row_frame(self, y, scale, plane, channel):
        if ROW_ACTIVE:
            row = 1 << y
        else:
            row = ~(1 << y) & 0xFF
        col = {name: (0xFF if COLOR_ACTIVE == 0 else 0x00) for name in _CHANNELS}
        i = _CHANNEL_INDEX[channel]
        byte = 0xFF if COLOR_ACTIVE == 0 else 0x00
        # original full-matrix column build (kept for reference):
        #     for x in range(_N_COLS):
        #         v = (self._fb[x][y][i] * scale) // 100
        #         q = v >> (8 - COLOR_BITS)
        #         if q & plane:
        #             if COLOR_ACTIVE == 0:
        #                 byte &= ~(1 << x)
        #             else:
        #                 byte |= 1 << x
        # CROP_COLS columns at the connector end are never lit: their bits
        # stay inactive, so those LEDs draw no current while the row scan
        # and the frame count remain unchanged.
        for x in range(_N_COLS):
            if CROP_COLS_FROM_HIGH:
                if x >= _N_COLS - CROP_COLS:
                    continue
            else:
                if x < CROP_COLS:
                    continue
            v = (self._fb[x][y][i] * scale) // 100
            q = v >> (8 - COLOR_BITS)
            if q & plane:
                if COLOR_ACTIVE == 0:
                    byte &= ~(1 << x)
                else:
                    byte |= 1 << x
        col[channel] = byte
        f = bytearray(4)
        f[0] = col[CHANNEL_ORDER[0]]
        f[1] = col[CHANNEL_ORDER[1]]
        f[2] = col[CHANNEL_ORDER[2]]
        f[3] = row
        return f

    def _rebuild(self):
        frames = []
        scale = self._brightness
        for bit in range(COLOR_BITS):
            plane = 1 << bit
            for _ in range(plane):
                for y in range(_N_ROWS):
                    for ch in _CHANNELS:
                        frames.append(self._row_frame(y, scale, plane, ch))
        self._frames = frames
        if self._dma_buf is not None:
            self._pack_buffer()
        self._dirty = False

    def _pack_buffer(self):
        buf = self._dma_buf
        for i, f in enumerate(self._frames):
            buf[i] = (f[0] << 24) | (f[1] << 16) | (f[2] << 8) | f[3]

    def _start_hw(self):
        if self._sm is not None:
            return
        import machine
        import rp2
        import uctypes
        from rp2 import PIO, StateMachine

        def prog():
            set(y, 31).side(0)
            label("bitloop")
            out(pins, 1).side(0)[1]
            jmp(y_dec, "bitloop").side(1)[1]
            nop().side(0)
            set(pins, 1)[2]
            set(pins, 0)[1]

        prog = rp2.asm_pio(
            out_init=(PIO.OUT_LOW,),
            sideset_init=PIO.OUT_LOW,
            set_init=(PIO.OUT_LOW,),
            out_shiftdir=PIO.SHIFT_LEFT,
            autopull=True,
            pull_thresh=32,
            fifo_join=PIO.JOIN_TX,
        )(prog)

        mem32 = machine.mem32
        sm = StateMachine(
            0,
            prog,
            freq=PIO_FREQ,
            out_base=self._mosi,
            set_base=self._latch,
            sideset_base=self._sck,
        )
        sm.active(1)
        self._sm = sm

        mem32[_DMA_BASE + 0x0C] = 0
        mem32[_DMA_BASE + 0x4C] = 0
        mem32[_DMA_CHAN_ABORT] = 0x3
        for _ in range(100):
            if not (mem32[_DMA_CHAN_ABORT] & 0x3):
                break
            time.sleep_ms(1)
        mem32[_DMA_BASE + 0x0C] = (1 << 30) | (1 << 29)
        mem32[_DMA_BASE + 0x4C] = (1 << 30) | (1 << 29)

        addr = uctypes.addressof(self._dma_buf)
        ch0 = _DMA_BASE
        ch1 = _DMA_BASE + 0x40
        slot = array("I", [addr])
        self._kick = slot

        mem32[ch1 + 0x00] = uctypes.addressof(slot)
        mem32[ch1 + 0x04] = ch0 + 0x3C
        mem32[ch1 + 0x08] = 1
        mem32[ch1 + 0x10] = _DMA_CTRL_CH1

        mem32[ch0 + 0x00] = addr
        mem32[ch0 + 0x04] = _PIO0_TXF0
        mem32[ch0 + 0x08] = len(self._frames)
        mem32[ch0 + 0x10] = _DMA_CTRL_CH0
        mem32[ch0 + 0x0C] = _DMA_CTRL_CH0

    def scan_loop(self, hook_ms=50, hook=None):
        self._start_hw()
        next_hook = time.ticks_ms()
        while True:
            if self._dirty:
                self._rebuild()
            if hook:
                now = time.ticks_ms()
                if time.ticks_diff(now, next_hook) >= 0:
                    next_hook = now + hook_ms
                    hook()
            time.sleep_ms(1)
