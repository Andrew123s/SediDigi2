# SediDigi/bg_led

Driving LED matrix panels from a Jetson Orin Nano.

| Approach | Directory | Status |
|----------|-----------|--------|
| **Jetson-based (SPI via GPIO)** | `jetson_ws2812/` | Implemented, **not working** — 3.3V logic level below WS2812B VIH spec |
| **Pico-based (USB Serial → PIO)** | `pico_ws2812/` | **Working** — PIO-driven WS2812 panel (5x5 or 8x8), controlled over USB Serial from the Jetson |
| **Pico 2-based (USB Serial → PIO + DMA)** | `pico_hc595/` | RGB 8x8 matrix ("LED Matrix 1.0", 4x 74HC595) with PIO/DMA refresh on a **Pico 2 (W)**, controlled over USB Serial from the Jetson — **not suitable** for the intended adaptive-color background use (banding at short exposures, low light output) |

## Project Structure

```
bg_led/
├── README.md               This file
├── jetson_ws2812/          Jetson-based SPI approach (superseded, not functional!)
│   ├── README.md           Technical setup documentation
│   ├── ws2812.py           WS2812 driver (spidev-based)
│   ├── demo.py             Color cycle demo
│   ├── test_spi_diag.py    SPI1 diagnostic checks
│   └── test_gpio.py        Pin 19 multimeter test
├── pico_ws2812/            Pico-based WS2812 5x5 / 8x8 solution
│   ├── device/             Runs on the Pico (panel server, demos)
│   ├── host/               Runs on the Jetson (pico_link.py/hpp, demo.py, blue1_perma.py, blue_dyn.py)
│   └── README.md           Full documentation incl. protocol spec
└── pico_hc595/             Pico 2 (W)-based RGB 8x8 matrix solution
    ├── device/             Runs on the Pico 2 (W) (driver, panel server, demos)
    ├── host/               Runs on the Jetson (pico_link.py/hpp, demo.py, blue1_perma.py)
    └── README.md           Full documentation incl. protocol spec
```

## Wiring Overview

```
External 5V Supply
  ├── 5V  ──► LED Matrix VCC
  └── GND ──► LED Matrix GND

jetson_ws2812 (superseded):  Jetson Pin 19 (SPI1_MOSI) ──► DIN
                             Jetson Pin 6  (GND)      ──► Matrix GND

pico_ws2812 (working):       Jetson USB ──► Pico (power + serial)
                             Pico GPIO 0  ──► DIN
                             Pico GND     ──► Matrix GND (shared)

pico_hc595:                  Jetson USB ──► Pico 2 (W) (power + serial)
                             Pico GPIO 19 ─► MOSI (SER)
                             Pico GPIO 18 ─► SCK (SRCLK)
                             Pico GPIO 17 ─► Latch (RCLK)
                             Pico GND     ─► Matrix GND (shared)
```

## Status

- [x] SPI driver implemented (`ws2812.py`)
- [x] SPI1 hardware configuration verified (device tree, pinmux, spidev mapping)
- [x] Root cause identified: **3.3V below WS2812B VIH (3.5V)**
- [x] Implement Pico variant (WS2812 5x5, `pico_ws2812/`)
- [x] Implement communication via USB between Jetson Orin Nano and Pico
      (`pico_ws2812/host/` + `pico_ws2812/device/panel_server.py`)
- [x] Implement Pico 2 (W) RGB 8x8 matrix variant (74HC595, `pico_hc595/`)
- [x] Same USB serial protocol across panels (`SET RRGGBB`, `OFF`, `PING`,
      `VERSION`)
- [x] Practical test (pico_hc595): banding at short exposures, exposure up
      to ~50 ms needed, low light output, no light homogeneity — verdict:
      not suitable for the intended use
- [x] Practical test (pico_ws2812): blue1_perma.py and blue_dyn.py run at
      50 % brightness without flicker or dropouts — panel suitable as a
      static or even slowly cycling color background

## References

- [WS2812B datasheet](https://www.ledyilighting.com/wp-content/uploads/2025/02/WS2812B-datasheet.pdf)
- [Jetson Orin Nano Carrier Board Specification](https://developer.download.nvidia.com/assets/embedded/secure/jetson/orin_nano/docs/Jetson-Orin-Nano-DevKit-Carrier-Board-Specification_SP-11324-001_v1.3.pdf)
