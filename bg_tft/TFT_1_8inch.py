import config
import Jetson.GPIO as GPIO
import time
import logging

TFT_WIDTH  = 128
TFT_HEIGHT = 160

# FRMCTR1 presets (register 0xB1). Select one index below.
_FRMCTR1_PRESETS = [
    (0x31, 0x1D, 0x1D),   # 0: 21 fps ×4 → 84 Hz   (optimal)
    (0x51, 0x01, 0x07),   # 1: 20 fps ×5 → 100 Hz  (optimal)
    (0x01, 0x0B, 0x3F),   # 2: 30 fps ×3 → 90 Hz   (optimal)
    (0x01, 0x01, 0x0E),   # 3: 60 fps ×2 → 120 Hz  (optimal)
    (0xF1, 0x3F, 0x3F),   # 4: 21 fps     → 42 Hz   (worst case)
]
_FRMCTR1_INDEX = 0   # ← change this index to select a preset

class TFT_1_8inch(object):
    def __init__(self):
        self.width = TFT_WIDTH
        self.height = TFT_HEIGHT
        self._dc = config.DC_PIN
        self._rst = config.RST_PIN
        self._benchmark = False

    def set_benchmark(self, enable):
        self._benchmark = enable

    def command(self, cmd):
        GPIO.output(self._dc, GPIO.LOW)
        config.spi_writebyte(cmd)

    def data(self, data):
        GPIO.output(self._dc, GPIO.HIGH)
        config.spi_writebyte(data)

    def reset(self):
        GPIO.output(self._rst, GPIO.HIGH)
        time.sleep(0.1)
        GPIO.output(self._rst, GPIO.LOW)
        time.sleep(0.1)
        GPIO.output(self._rst, GPIO.HIGH)
        time.sleep(0.1)

    def Init(self):
        if config.module_init() != 0:
            return -1
        self.width = TFT_WIDTH
        self.height = TFT_HEIGHT
        self.reset()

        self.command(0x01)
        time.sleep(0.15)
        self.command(0x11)
        time.sleep(0.15)

        self.command(0xB1)
        rtna, fpa, bpa = _FRMCTR1_PRESETS[_FRMCTR1_INDEX]
        self.data(rtna)
        self.data(fpa)
        self.data(bpa)

        self.command(0xB2)
        self.data(0x01)
        self.data(0x2C)
        self.data(0x2D)

        self.command(0xB3)
        self.data(0x01)
        self.data(0x2C)
        self.data(0x2D)
        self.data(0x01)
        self.data(0x2C)
        self.data(0x2D)

        self.command(0xB4)
        self.data(0x07)

        self.command(0xC0)
        self.data(0xA2)
        self.data(0x02)
        self.data(0x84)

        self.command(0xC1)
        self.data(0xC5)

        self.command(0xC2)
        self.data(0x0A)
        self.data(0x00)

        self.command(0xC3)
        self.data(0x8A)
        self.data(0x2A)

        self.command(0xC4)
        self.data(0x8A)
        self.data(0xEE)

        self.command(0xC5)
        self.data(0x0E)

        self.command(0x36)
        self.data(0x00)

        self.command(0x3A)
        self.data(0x05)

        self.command(0x2A)
        self.data(0x00)
        self.data(0x00)
        self.data(0x00)
        self.data(0x7F)

        self.command(0x2B)
        self.data(0x00)
        self.data(0x00)
        self.data(0x00)
        self.data(0x9F)

        self.command(0x13)
        time.sleep(0.01)
        self.command(0x29)

        return 0

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
        self.command(0x2A)
        self.data(0x00)
        self.data(0x00)
        self.data(0x00)
        self.data(0x7F)
        self.command(0x2B)
        self.data(0x00)
        self.data(0x00)
        self.data(0x00)
        self.data(0x9F)
        self.command(0x2C)
        GPIO.output(self._dc, GPIO.HIGH)
        config.spi_writebytes(pBuf)
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
