#!/usr/bin/python3
import logging
import os
import time
import OLED_1_5inch_rgb
from PIL import Image

logging.basicConfig(level=logging.DEBUG)

try:
    disp = OLED_1_5inch_rgb.OLED_1_5inch_rgb()
    
    logging.info("1.5inch RGB OLED")
    disp.Init()
    
    # optional: activate benchmark
    disp.set_benchmark(not True)
    
    logging.info("1) clear display")
    disp.clear()
	
    logging.info("2) draw image")
    Himage2 = Image.new('RGB', (disp.width, disp.height), 0)
    bmp = Image.open('logo.bmp')
    Himage2.paste(bmp, (0,0))
    Himage2 = Himage2.rotate(0)
    disp.ShowImage(disp.getbuffer(Himage2))
    time.sleep(3)

    logging.info("3) fill screen with one color")
    colors = ['0062ac', '17388c', '0083c9', '0079ba', '0063ac', '006bb5', '00599f']
    for i, col in enumerate(colors, 1):
        logging.info(f"color {i}/{len(colors)}: #{col}")
        disp.FillColor(col)
        time.sleep(3)

    logging.info("4) show color images")
    for i, f in enumerate(sorted(os.listdir('bgimages')), 1):
        img = Image.open(f'bgimages/{f}')
        buf = disp.getbuffer(img)
        logging.info(f"Image {i}/7: {f}")
        disp.ShowImage(buf)
        time.sleep(3)

    disp.clear()

except IOError as e:
    logging.info(e)

except KeyboardInterrupt:
    logging.info("ctrl + c:")
    disp = None
    exit()
