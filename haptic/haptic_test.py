# -*- coding: utf-8 -*-
"""
haptic_test.py - Test script for TM6605 via PCA9548A multiplexer

Scans MUX channels 0-3 for TM6605 modules and plays an effect on each.
"""
import sys
import time

from DFRobot_TM6605 import DFRobot_TM6605
from PCA9548A import PCA9548A

MUX_BUS = 1
MUX_ADDRESS = 0x70
CHANNELS = [0, 1, 2, 3]

# See DFRobot_TM6605.py for other effects and their IDs
##EFFECT = 10  # double_click
##EFFECT = 88  # long_fast_boost_transition_1 
##EFFECT = 1   # sharp_click

# preferred effect:
# 1x short impulse / 1x long impulse
EFFECT1 = 1
EFFECT2 = 70
SEQUENCE = "short_long"  # = EFFECT1 + EFFECT2 in sequence (functional control)

EFFECT3 = 4
EFFECT4 = 82
SEQUENCE2 = "short_long_soft"  # = EFFECT3 + EFFECT4 in sequence (softer variant)

mux = PCA9548A(bus=MUX_BUS, address=MUX_ADDRESS)
print("PCA9548A initialized on bus {} (address 0x{:02x})".format(MUX_BUS, MUX_ADDRESS))
print("Scanning channels {} for TM6605 modules...".format(CHANNELS))
print()

found = 0
found_channels = []
for ch in CHANNELS:
    mux.select_channel(ch)
    tm = DFRobot_TM6605(bus=MUX_BUS)
    if tm.begin() != 0:
        print("Channel {}: no device found (skipped)".format(ch))
        continue

    print("Channel {}: TM6605 found. ".format(ch), end="")
    ##tm.select_effect(EFFECT1)
    ##tm.play()
    ##print(" -> playing effect {}".format(EFFECT1))
    ##time.sleep(0.5)
    ##tm.select_effect(EFFECT2)
    ##tm.play()
    ##print(" -> playing effect {}".format(EFFECT2))
    ##time.sleep(0.5)
    ##tm.stop()
    print("Channel {}: playing sequence {}".format(ch, SEQUENCE), end="\n")
    tm.play_sequence(SEQUENCE)
    tm.stop()
    ##print(" (same as effects {} + {} in sequence)".format(EFFECT1, EFFECT2))
    print("Channel {}: playing sequence {}".format(ch, SEQUENCE2), end="\n")
    tm.play_sequence(SEQUENCE2)
    tm.stop()
    found += 1
    found_channels.append(ch)

print()

# synchronous broadcast test over all detected channels
if found_channels:
    mask = 0
    for ch in found_channels:
        mask |= (1 << ch)
    print("Testing synchronous playback on channels {} (mask 0x{:02x}) ...".format(found_channels, mask))
    tm = DFRobot_TM6605(bus=MUX_BUS)
    mux.select_channels(mask)
    tm.play_sequence(SEQUENCE)
    tm.stop()
    print(" -> played sequence '{}' simultaneously on {}".format(SEQUENCE, found_channels))
    tm.play_sequence(SEQUENCE2)
    tm.stop()
    mux.deselect()
    print(" -> played sequence '{}' simultaneously on {}".format(SEQUENCE2, found_channels))
    print()

if found == 0:
    print("No TM6605 module found on any channel")
    sys.exit(1)
else:
    print("Done: {} module(s) tested".format(found))
