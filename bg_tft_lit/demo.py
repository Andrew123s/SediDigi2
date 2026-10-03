#!/usr/bin/python3
import logging
import os
import time
import config
import TFT_3_5inch
from PIL import Image

logging.basicConfig(level=logging.DEBUG)

try:
    config.pwm_init(80)
    disp = TFT_3_5inch.TFT_3_5inch()

    logging.info("ILI9488 3.5inch TFT (320x480)")
    disp.Init()

    disp.set_benchmark(not True)

    logging.info("1) clear display")
    disp.clear()

    logging.info("2) draw logo")
    logo = Image.open('logo.bmp')
    disp.ShowImage(disp.getbuffer(logo))
    time.sleep(5)

    logging.info("3) fill screen with one color")
    colors = ['0062ac', '17388c', '0083c9', '0079ba', '0063ac', '006bb5', '00599f']
    for i, col in enumerate(colors, 1):
        logging.info(f"color {i}/{len(colors)}: #{col}")
        disp.FillColor(col)
        time.sleep(5)

    logging.info("4) show color images (fullscreen)")
    for i, f in enumerate(sorted(os.listdir('bgimages')), 1):
        img = Image.open(f'bgimages/{f}')
        logging.info(f"Image {i}/7: {f}")
        disp.ShowImage(disp.getbuffer(img))
        time.sleep(5)

    disp.clear()

except IOError as e:
    logging.info(e)

except KeyboardInterrupt:
    logging.info("ctrl + c:")

finally:
    config.module_exit()
