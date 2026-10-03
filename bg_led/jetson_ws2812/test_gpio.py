#!/usr/bin/python3
"""GPIO test for Jetson Orin Nano Pin 19 (SPI1_MOSI).

Toggles Pin 19 HIGH (3.3V) for 10 s, then LOW (0V) for 10 s.
Use a multimeter or scope to verify the voltage levels.

Usage:  sudo python3 test_gpio.py
"""

import Jetson.GPIO as GPIO
import time

GPIO.setmode(GPIO.TEGRA_SOC)
GPIO.setup("GP49_SPI1_MOSI", GPIO.OUT)

print("Pin 19 HIGH (3.3V) — measure now...")
GPIO.output("GP49_SPI1_MOSI", 1)
time.sleep(10)

print("Pin 19 LOW (0V) — measure now...")
GPIO.output("GP49_SPI1_MOSI", 0)
time.sleep(10)

GPIO.cleanup()
print("Done.")
