#!/usr/bin/python3
import logging
import time
from ws2812 import WS2812

logging.basicConfig(level=logging.DEBUG)

try:
    matrix = WS2812(num_leds=25, brightness=0.5)
    matrix.Init()

    logging.info("1) Red")
    matrix.set_color("FF0000")
    time.sleep(3)

    logging.info("2) Green")
    matrix.set_color("00FF00")
    time.sleep(3)

    logging.info("3) Blue")
    matrix.set_color("0000FF")
    time.sleep(3)

    blue_tones = [
        ("Blue 1", "0062ac"),
        ("Blue 2", "17388c"),
        ("Blue 3", "0083c9"),
        ("Blue 4", "0079ba"),
        ("Blue 5", "0063ac"),
        ("Blue 6", "006bb5"),
        ("Blue 7", "00599f"),
    ]
    for i, (name, hex_color) in enumerate(blue_tones, 1):
        logging.info(f"4.{i}) {name} (#{hex_color})")
        matrix.set_color(hex_color)
        time.sleep(2)

    logging.info("5) White @ 25% brightness")
    matrix.set_brightness(0.25)
    matrix.set_color("FFFFFF")
    time.sleep(3)

    logging.info("6) White @ 50% brightness")
    matrix.set_brightness(0.50)
    time.sleep(3)

    logging.info("7) White @ 100% brightness")
    matrix.set_brightness(1.00)
    time.sleep(3)

    matrix.clear()

except KeyboardInterrupt:
    logging.info("ctrl + c:")

finally:
    matrix.module_exit()
