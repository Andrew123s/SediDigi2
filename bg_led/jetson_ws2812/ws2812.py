#!/usr/bin/python3
import logging
import spidev

logging.basicConfig(level=logging.DEBUG)

SPI_DEVICE = 0
SPI_CHIP = 0
SPI_SPEED = 6400000

BIT0 = 0b11000000
BIT1 = 0b11110000

RESET_BYTES = 350


class WS2812:
    def __init__(self, num_leds=25, brightness=0.5):
        self.num_leds = num_leds
        self.brightness = brightness
        self._raw_color = (0, 0, 0)
        self.spi = None

    def Init(self):
        self.spi = spidev.SpiDev(SPI_DEVICE, SPI_CHIP)
        self.spi.max_speed_hz = SPI_SPEED
        self.spi.mode = 0b00
        logging.info(
            f"WS2812 initialized: {self.num_leds} LEDs, "
            f"brightness={self.brightness}, "
            f"SPI={SPI_DEVICE}.{SPI_CHIP} @ {SPI_SPEED / 1e6}MHz"
        )

    def _encode_ws2812(self, r, g, b):
        data = bytearray(24)
        for byte_idx, val in enumerate((g, r, b)):
            for bit_idx in range(8):
                data[byte_idx * 8 + bit_idx] = BIT1 if val & (1 << (7 - bit_idx)) else BIT0
        return data

    def set_color(self, hex_color):
        hex_color = hex_color.lstrip('#')
        self._raw_color = (
            int(hex_color[0:2], 16),
            int(hex_color[2:4], 16),
            int(hex_color[4:6], 16),
        )
        self._update()
        logging.info(f"Color set to #{hex_color}")

    def set_brightness(self, value):
        self.brightness = max(0.0, min(1.0, value))
        self._update()
        logging.info(f"Brightness set to {self.brightness:.0%}")

    def _update(self):
        r = int(self._raw_color[0] * self.brightness)
        g = int(self._raw_color[1] * self.brightness)
        b = int(self._raw_color[2] * self.brightness)
        data = self._encode_ws2812(r, g, b) * self.num_leds
        data += bytes(RESET_BYTES)
        self.spi.writebytes(list(data))

    def clear(self):
        self._raw_color = (0, 0, 0)
        self._update()
        logging.info("All LEDs off")

    def module_exit(self):
        self.clear()
        if self.spi:
            self.spi.close()
        logging.info("WS2812 cleanup done")
