import config
import Jetson.GPIO as GPIO
import time
import logging

TFT_WIDTH  = 320
TFT_HEIGHT = 480

# FRMCTR1 presets (register 0xB1). Select one index below.
_FRMCTR1_PRESETS = [
    0xA0,   # 0: 60 fps ×1 / 30 fps ×2 → 60.8 Hz
    0x98,   # 1: 21 fps ×3          → 64.0 Hz
]
_FRMCTR1_INDEX = 1   # ← change this index to select a preset

class TFT_3_5inch(object):
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

        # 0x01 – Software Reset
        self.command(0x01)
        time.sleep(0.15)
        # 0x11 – Sleep Out
        self.command(0x11)
        time.sleep(0.15)

        # 0x3A – Interface Pixel Format: RGB666 (18-bit, 3 bytes/pixel)
        self.command(0x3A)
        self.data(0x66)

        # 0x36 – Memory Access Control: BGR, portrait (MX=0, MY=0, MV=0, BGR=1)
        self.command(0x36)
        self.data(0x08)

        # 0xB0 – Interface Mode Control: disable DPI/DSI bypass
        self.command(0xB0)
        self.data(0x00)

        # 0xB1 – Frame Rate Control (Normal Mode): select FRMCTR1 preset
        self.command(0xB1)
        self.data(_FRMCTR1_PRESETS[_FRMCTR1_INDEX])

        # 0xB4 – Display Inversion Control: 2-dot inversion
        self.command(0xB4)
        self.data(0x02)

        # 0xB6 – Display Function Control: RGB interface, gate/source timing
        self.command(0xB6)
        self.data(0x02)
        self.data(0x42)

        # 0xC0 – Power Control 1: VREG1OUT / VGH voltage
        self.command(0xC0)
        self.data(0x1E)
        self.data(0x1E)

        # 0xC1 – Power Control 2: VGH / VGL charge pump
        self.command(0xC1)
        self.data(0x43)

        # 0xC2 – Power Control 3 (Normal Mode): VREG2OUT voltage
        self.command(0xC2)
        self.data(0x33)

        # 0xC5 – VCOM Control: VCOMH / VCOML voltage
        self.command(0xC5)
        self.data(0x00)
        self.data(0x3C)
        self.data(0x00)

        # 0xC6 – CABC Control 1: content adaptive brightness
        # Once disabled – left at reset default (CABC off) to avoid flicker potential.
        self.command(0xC6)
        self.data(0x00)
        self.data(0x02)

        # 0xE0 – Positive Gamma Correction (15 values)
        self.command(0xE0)
        for val in (0x0F, 0x1F, 0x1C, 0x0C, 0x0F, 0x08, 0x48, 0x98,
                    0x37, 0x0A, 0x13, 0x04, 0x11, 0x0D, 0x00):
            self.data(val)

        # 0xE1 – Negative Gamma Correction (15 values)
        self.command(0xE1)
        for val in (0x0F, 0x32, 0x2E, 0x0B, 0x0D, 0x05, 0x47, 0x75,
                    0x37, 0x06, 0x10, 0x03, 0x24, 0x20, 0x00):
            self.data(val)

        # 0xE2 – Digital Gamma Control (15 values)
        self.command(0xE2)
        for val in (0x0F, 0x32, 0x2E, 0x0B, 0x0D, 0x05, 0x47, 0x75,
                    0x37, 0x06, 0x10, 0x03, 0x24, 0x20, 0x00):
            self.data(val)

        # 0x11 – Sleep Out (wake from sleep)
        self.command(0x11)
        time.sleep(0.15)
        # 0x29 – Display ON
        self.command(0x29)
        time.sleep(0.05)

        return 0

    def clear(self):
        _buffer = [0x00] * (self.width * self.height * 3)
        self.ShowImage(_buffer)

    def _rgb666(self, r, g, b):
        return (r & 0xFC, g & 0xFC, b & 0xFC)

    def getbuffer(self, image):
        if self._benchmark:
            _start = time.perf_counter()
        buf = [0x00] * ((self.width * 3) * self.height)
        imwidth, imheight = image.size
        pixels = image.load()
        for y in range(imheight):
            for x in range(imwidth):
                r, g, b = pixels[x, y][:3]
                idx = (x * 3) + (y * imwidth * 3)
                buf[idx]     = r & 0xFC
                buf[idx + 1] = g & 0xFC
                buf[idx + 2] = b & 0xFC
        if self._benchmark:
            _elapsed = (time.perf_counter() - _start) * 1000
            logging.info(f"[Benchmark] getbuffer: {_elapsed:.1f} ms")
        return buf

    def _set_window(self):
        self.command(0x2A)
        self.data(0x00)
        self.data(0x00)
        self.data(0x01)
        self.data(0x3F)
        self.command(0x2B)
        self.data(0x00)
        self.data(0x00)
        self.data(0x01)
        self.data(0xDF)

    def ShowImage(self, pBuf):
        if self._benchmark:
            _start = time.perf_counter()
        self._set_window()
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
        b0, b1, b2 = self._rgb666(r, g, b)
        _buffer = [b0, b1, b2] * (self.width * self.height)
        self.ShowImage(_buffer)
        if self._benchmark:
            _elapsed = (time.perf_counter() - _start) * 1000
            logging.info(f"[Benchmark] FillColor: {_elapsed:.1f} ms")
