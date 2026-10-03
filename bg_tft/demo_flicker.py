#!/usr/bin/python3
import logging
import time
import TFT_1_8inch

logging.basicConfig(level=logging.DEBUG)

disp = TFT_1_8inch.TFT_1_8inch()
disp.Init()
disp.set_benchmark(not True)
disp.clear()

logging.info("Flicker test: alternating white (#FFFFFF) / black (#000000)")
try:
    while True:
        disp.FillColor("#FFFFFF")
        time.sleep(0.2)
        disp.FillColor("#000000")
        time.sleep(0.2)
except KeyboardInterrupt:
    disp.clear()
