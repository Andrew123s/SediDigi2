import rp2
import time
import gc
import sys
from machine import Pin, disable_irq, enable_irq

NUM_LEDS = 25          # 25 for 5×5 panel, 64 for 8×8 panel
DEFAULT_BRIGHTNESS = 50
PROTOCOL_VERSION = 1


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


def set_panel(hex_color, brightness):
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    scale = brightness / 100
    show([(int(r * scale), int(g * scale), int(b * scale))])


def turn_off():
    show([(0, 0, 0)])


def respond(msg):
    print(msg)


def parse(line):
    parts = line.split()
    if not parts:
        return
    cmd = parts[0].upper()

    if cmd == "SET" and len(parts) >= 2:
        hex_color = parts[1].lower()
        if len(hex_color) != 6 or not all(c in "0123456789abcdef" for c in hex_color):
            respond("ERR invalid color")
            return
        brightness = DEFAULT_BRIGHTNESS
        if len(parts) >= 3:
            try:
                brightness = int(parts[2])
            except ValueError:
                respond("ERR invalid brightness")
                return
            if not 0 <= brightness <= 100:
                respond("ERR brightness must be 0-100")
                return
        set_panel(hex_color, brightness)
        respond("OK")
    elif cmd == "OFF":
        turn_off()
        respond("OK")
    elif cmd == "PING":
        respond("PONG")
    elif cmd == "VERSION":
        respond("VERSION %d" % PROTOCOL_VERSION)
    else:
        respond("ERR unknown command")


def main():
    while True:
        line = sys.stdin.buffer.readline()
        if line is None or line == b"":
            continue
        try:
            parse(line.decode("utf-8"))
        except Exception as e:
            respond("ERR %s" % e)


main()
