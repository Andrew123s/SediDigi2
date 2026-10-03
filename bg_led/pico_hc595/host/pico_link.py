#!/usr/bin/env python3
"""Jetson-side client for the Pico RGB matrix panel server.

Talks the line-based USB serial protocol specified in README.md
(section "USB Serial Protocol").

The panel is an 8x8 RGB matrix ("LED Matrix 1.0", 4x 74HC595) driven by a
Pico 2 (W); the color value is applied as-is.

Usage (CLI):
    python3 pico_link.py PING
    python3 pico_link.py SET 0062ac 40
    python3 pico_link.py SET 0062ac
    python3 pico_link.py OFF
    python3 pico_link.py VERSION
"""

import argparse
import sys

import serial


class ProtocolError(Exception):
    """Raised when the Pico replies with ERR."""


class PicoLink:
    DEVICE = "/dev/ttyACM0"
    TIMEOUT = 2.0

    def __init__(self, device=None, timeout=None):
        self._ser = serial.Serial(
            device or self.DEVICE,
            baudrate=115200,
            timeout=timeout or self.TIMEOUT,
        )

    def send(self, command):
        self._ser.write((command + "\n").encode("ascii"))
        line = self._ser.readline().decode("utf-8", errors="replace").strip()
        if line.startswith("ERR "):
            raise ProtocolError(line[4:])
        return line

    def set_color(self, hex_color, brightness=50):
        return self.send("SET {} {}".format(hex_color, brightness))

    def off(self):
        return self.send("OFF")

    def ping(self):
        return self.send("PING")

    def version(self):
        return self.send("VERSION")

    def close(self):
        self._ser.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def main():
    parser = argparse.ArgumentParser(description="Control the Pico RGB matrix panel server")
    parser.add_argument("command", choices=["SET", "OFF", "PING", "VERSION"])
    parser.add_argument("color", nargs="?", help="hex color RRGGBB (for SET)")
    parser.add_argument("brightness", nargs="?", type=int, help="brightness 0-100, default 50 (for SET)")
    parser.add_argument("--device", default=PicoLink.DEVICE, help="serial device path")
    args = parser.parse_args()

    if args.command == "SET" and not args.color:
        parser.error("SET requires a color, e.g. SET 0062ac 40")

    try:
        with PicoLink(device=args.device) as link:
            if args.command == "SET":
                brightness = args.brightness if args.brightness is not None else 50
                response = link.set_color(args.color, brightness)
            elif args.command == "OFF":
                response = link.off()
            elif args.command == "PING":
                response = link.ping()
            elif args.command == "VERSION":
                response = link.version()
        cmd_text = " ".join(
            part for part in (args.command, args.color, str(brightness)) if part
        ) if args.command == "SET" else args.command
        print("{} -> {}".format(cmd_text, response))
    except (serial.SerialException, ProtocolError) as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
