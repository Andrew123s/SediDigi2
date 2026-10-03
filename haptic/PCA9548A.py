# -*- coding: utf-8 -*-
"""
PCA9548A.py - I2C Multiplexer Driver for PCA9548A/TCA9548A

Provides channel selection for the 8-channel I2C multiplexer.
Compatible with both PCA9548A and TCA9548A.
"""
from smbus import SMBus

class PCA9548A:
    def __init__(self, bus=1, address=0x70):
        self.bus = SMBus(bus)
        self.address = address

    def select_channel(self, channel):
        if channel < 0 or channel > 7:
            raise ValueError("Channel must be 0-7")
        self.bus.write_byte(self.address, 1 << channel)

    def select_channels(self, channel_mask):
        if channel_mask < 0 or channel_mask > 0xFF:
            raise ValueError("Channel mask must be 0-255")
        self.bus.write_byte(self.address, channel_mask)

    def deselect(self):
        self.bus.write_byte(self.address, 0x00)
