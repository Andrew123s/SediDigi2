# SediDigi/bg_led/jetson_ws2812

> **Superseded.** This Jetson-based (SPI) approach is **not functional** —
> the 3.3V GPIO logic level is below the WS2812B V4/V5 VIH spec (≥3.5V). The
> working solution is the Pico-based one in `../pico_ws2812/`. This folder is
> kept for reference and diagnostics only.

SPI-based driver for controlling a Joycabin 25bit WS2812B 5x5 LED matrix
directly from the Jetson Orin Nano's 40-pin GPIO header.

**This approach is limited by the 3.3V GPIO logic level (WS2812B V4/V5
requires VIH >= 3.5V).** A level shifter or the Pico variant is needed for
reliable operation.

## Files

- **`ws2812.py`** — Driver module (spidev-based)
- **`demo.py`** — Demo script: color cycling and brightness control
- **`test_spi_diag.py`** — SPI1 diagnostics (10 checks)
- **`test_gpio.py`** — Pin 19 voltage verification

## Pinout & Wiring

| Matrix Pin | Jetson Pin | Note |
|------------|-----------|------|
| DIN | Pin 19 (SPI1_MOSI) | 330 ohm optional (recommended) |
| GND (Signal) | Pin 6 (GND) | Shared ground reference |
| 5V / VCC | External 5V supply | **Do not use Jetson 5V pins** |
| GND (Power) | External supply GND | Same plane as signal GND |

> The matrix has two GND pads on the input side. Both are connected to the
> same ground plane on the PCB. The power-side GND is already occupied by
> the external supply; the remaining GND pad serves as signal reference and
> must be connected to the Jetson Pin 6.

> **Do not power the matrix from the Jetson's 5V header pins (2 or 4).**
> The Orin Nano carrier board limits current on these pins to 1A max.

### Wiring Diagram

```
External 5V Supply (>1.5A)      WS2812B 5x5 Matrix         Jetson Orin Nano
──────────────────────────      ──────────────────         ─────────────────
 5V ────────────────────────►   5V / VCC
 GND ──┬────────────────────►   GND (Power)
        │
        └─────────────────────  GND (Signal) ◄─────────  Pin 6 (GND)

                                   DIN ◄── Pin 19 (SPI1_MOSI)
```

## Software Setup

### Enable SPI1 via jetson-io

```bash
sudo /opt/nvidia/jetson-io/jetson-io.py
```

- Select **"Configure Jetson 40pin Header"**
- Select **"Configure header pins manually"**
- Enable **SPI1** (pins 19, 21, 23, 24, 26)
- Save, exit, and **reboot**

After reboot, verify SPI1 devices:

```bash
ls /dev/spidev0.*
# Expected: /dev/spidev0.0  /dev/spidev0.1
```

> **Important:** On Jetson Orin Nano, SPI1 (40-pin header) maps to
> `spi@3210000` → `/dev/spidev0.0`. The other controller `spi@3230000`
> (SPI3/internal) maps to `spidev1.0`. Verified via `of_node` symlinks.

If SPI devices do not appear:

```bash
sudo modprobe spidev
```

### Install dependencies

```bash
sudo apt install python3-pip
sudo pip3 install spidev
```

### Run the demo

```bash
sudo python3 demo.py
```

The demo cycles through red, green, blue (3s each), then seven blue tones
from `bg_tft/colors_config.json`, then white at 25/50/100% brightness.

### Run diagnostics

```bash
sudo python3 test_spi_diag.py
```

10 checks covering device files, SPI master mapping, device tree status,
pinmux, GPIO allocation, spidev open/write, overlay status, and live pinmux.

## API Reference

```python
from ws2812 import WS2812

matrix = WS2812(num_leds=25, brightness=0.5)
matrix.Init()
```

| Method | Parameter | Description |
|--------|-----------|-------------|
| `Init()` | — | Open SPI1, configure encoding |
| `set_color(hex)` | `"FF8800"` | Set all 25 LEDs to color |
| `set_brightness(v)` | `0.0`–`1.0` | Set global brightness |
| `clear()` | — | Turn off all LEDs |
| `module_exit()` | — | Clear LEDs, close SPI |

## Technical Notes

- **SPI bus:** `spidev.SpiDev(0, 0)` → `spi@3210000` (SPI1, verified via of_node)
- **Color order:** WS2812B = GRB (driver handles encoding)
- **SPI freq:** 6.4 MHz — bit0=`0b11000000`, bit1=`0b11110000` (8 SPI bits per WS2812B bit)
- **Reset:** 350 bytes of 0x00 (~437 us at 6.4 MHz, >= 280 us spec)
- **Max current:** 25 LEDs x 60 mA = 1.5 A at full white
- **Common ground:** External PSU GND and Jetson GND must share reference
- **3.3V level:** Jetson outputs 3.3V; WS2812B V4/V5 need >= 3.5V VIH. V6 chips (post Sep 2025) accept 3.0V.

## Known Platform Issues

| Issue | Detail |
|-------|--------|
| `board.SPI()` (Blinka) | Opens `spidev0.0` but maps to SPI3, not SPI1 |
| `NeoPixel_SPI` reset | Default 80 us too short; >= 280 us required |
| Device tree null bytes | `/proc/device-tree/` values have `\x00` terminators |
| Pinmux | `2430000.pinmux` with HOG entries (Tegra234 specific) |

## References

- [WS2812B datasheet](https://www.ledyilighting.com/wp-content/uploads/2025/02/WS2812B-datasheet.pdf)
- [Jetson Orin SPI Overlay Guide](https://github.com/jetsonhacks/jetson-orin-spi-overlay-guide)
- [Adafruit NeoPixel SPI](https://docs.circuitpython.org/projects/neopixel_spi/en/stable/api.html)
