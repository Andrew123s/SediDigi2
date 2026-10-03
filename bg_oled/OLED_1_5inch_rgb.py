import config
import Jetson.GPIO as GPIO
import time
import logging
import numpy as np

Device_SPI = config.Device_SPI
Device_I2C = config.Device_I2C

OLED_WIDTH  = 128
OLED_HEIGHT = 128


class OLED_1_5inch_rgb(object):
    def __init__(self):
        self.width = OLED_WIDTH
        self.height = OLED_HEIGHT
        self._dc = config.DC_PIN
        self._rst = config.RST_PIN
        self.Device = config.Device
        self._benchmark = False

    def set_benchmark(self, enable):
        self._benchmark = enable

    def command(self, cmd):
        GPIO.output(self._dc, GPIO.LOW)
        config.spi_writebyte([cmd])

    def data(self, data):
        GPIO.output(self._dc, GPIO.HIGH)
        config.spi_writebyte([data])

    def Init(self):
        if config.module_init() != 0:
            return -1
        self.width = OLED_WIDTH
        self.height = OLED_HEIGHT
        self.reset()

        if self.Device == Device_I2C:
            print("Only Device_SPI, Please revise config.py!")
            exit()

        self.command(0xfd)
        self.data(0x12)
        self.command(0xfd)
        self.data(0xB1)

        self.command(0xae)
        self.command(0xa4)

        self.command(0x15)
        self.data(0x00)
        self.data(0x7f)
        self.command(0x75)
        self.data(0x00)
        self.data(0x7f)

        # REFRESH RATE TUNING Part 1
        # Front Clock Divider / Oscillator Frequency
        #
        # Register 0xB3: 
        # [7:4] = oscillator frequency (0x0..0xF, higher = faster)
        # [3:0] = DCLK divider (DCLK = CLK / (divider + 1))
        #
        self.command(0xB3)
        # 0xF1 → max oscillator, divider=1 → DCLK = CLK/2 (default)
        ##self.data(0xF1)
        # 0xF0 → max oscillator, divider=0 → DCLK = CLK/1
        self.data(0xF0)

        self.command(0xCA)
        self.data(0x7F)

        self.command(0xa0)
        self.data(0x74)

        self.command(0xa1)
        self.data(0x00)

        self.command(0xa2)
        self.data(0x00)

        self.command(0xAB)
        self.command(0x01)

        self.command(0xB4)
        self.data(0xA0)
        self.data(0xB5)
        self.data(0x55)

        self.command(0xC1)
        self.data(0xC8)
        self.data(0x80)
        self.data(0xC0)

        self.command(0xC7)
        self.data(0x0F)

        # REFRESH RATE TUNING Part 2
        # Phase Length (Pre-Charge + Drive)
        #
        # Register 0xB1: 
        # [7:4] = Phase 2 (drive period in DCLK cycles)
        # [3:0] = Phase 1 (pre-charge period in DCLK cycles)
        #
        # Frame duration ≈ (Phase1 + Phase2) × 128 rows / DCLK
        # Smaller values = higher frame rate, but risk of display artifacts
        self.command(0xB1)
        # 0x32 → Phase1 = 2, Phase2 = 3 (default)
        ##self.data(0x32)
        #
        self.data(0x11)
	
        self.command(0xB2)
        self.data(0xA4)
        self.data(0x00)
        self.data(0x00)

        self.command(0xBB)
        self.data(0x17)

        self.command(0xB6)
        self.data(0x01)

        self.command(0xBE)
        self.data(0x05)

        self.command(0xA6)

        time.sleep(0.1)
        self.command(0xAF)

    def reset(self):
        GPIO.output(self._rst, GPIO.HIGH)
        time.sleep(0.1)
        GPIO.output(self._rst, GPIO.LOW)
        time.sleep(0.1)
        GPIO.output(self._rst, GPIO.HIGH)
        time.sleep(0.1)

    def clear(self):
        _buffer = [0x00] * (self.width * self.height * 2)
        self.ShowImage(_buffer)

    def getbuffer(self, image):
        if self._benchmark:
            _start = time.perf_counter()
        buf = [0x00] * ((self.width * 2) * self.height)
        imwidth, imheight = image.size
        pixels = image.load()
        for y in range(imheight):
            for x in range(imwidth):
                buf[x * 2 + y * imwidth * 2] = ((pixels[x, y][0] & 0xF8) | (pixels[x, y][1] >> 5))
                buf[x * 2 + 1 + y * imwidth * 2] = (((pixels[x, y][1] << 3) & 0xE0) | (pixels[x, y][2] >> 3))
        if self._benchmark:
            _elapsed = (time.perf_counter() - _start) * 1000
            logging.info(f"[Benchmark] getbuffer: {_elapsed:.1f} ms")
        return buf

    def ShowImage(self, pBuf):
        if self._benchmark:
            _start = time.perf_counter()
        self.command(0x15)
        self.data(0x00)
        self.data(0x7f)
        self.command(0x75)
        self.data(0x00)
        self.data(0x7f)
        self.command(0x5C)
        GPIO.output(self._dc, GPIO.HIGH)
        config.spi_write(pBuf)
        if self._benchmark:
            _elapsed = (time.perf_counter() - _start) * 1000
            logging.info(f"[Benchmark] ShowImage: {_elapsed:.1f} ms")

    def FillColor(self, hex_color):
        if self._benchmark:
            _start = time.perf_counter()
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        byte0 = ((r & 0xF8) | (g >> 5))
        byte1 = (((g << 3) & 0xE0) | (b >> 3))
        _buffer = [byte0, byte1] * (self.width * self.height)
        self.ShowImage(_buffer)
        if self._benchmark:
            _elapsed = (time.perf_counter() - _start) * 1000
            logging.info(f"[Benchmark] FillColor: {_elapsed:.1f} ms")

    def SetBrightness(self, level: int):
        level = max(0, min(15, level))
        self.command(0xC7)
        self.data(level)
