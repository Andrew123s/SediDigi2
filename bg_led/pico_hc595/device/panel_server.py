import select
import sys
from machine import Pin

import hc595_rgb

DEFAULT_BRIGHTNESS = 50
PROTOCOL_VERSION = 2

latch = Pin(17, Pin.OUT, value=0)
panel = hc595_rgb.HC595RGB(Pin(19), Pin(18), latch)


def set_panel(hex_color, brightness):
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    panel.brightness(brightness)
    panel.fill(r, g, b)


def turn_off():
    panel.fill(0, 0, 0)


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
    poller = select.poll()
    poller.register(sys.stdin, select.POLLIN)

    def hook():
        while poller.poll(0):
            line = sys.stdin.buffer.readline()
            if not line:
                continue
            try:
                parse(line.decode("utf-8"))
            except Exception as e:
                respond("ERR %s" % e)

    panel.scan_loop(hook_ms=10, hook=hook)


main()
