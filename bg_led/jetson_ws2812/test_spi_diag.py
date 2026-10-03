#!/usr/bin/python3
"""SPI1 diagnostics for Jetson Orin Nano.

Checks whether SPI1 is properly configured on the 40-pin header so that
the correct spidev device is usable for driving WS2812B LEDs.

Key finding: On Jetson Orin Nano, SPI1 (40-pin header) maps to
spi@3210000 -> spidev0.0, NOT spi@3230000 -> spidev1.0.

The device tree nodes are under bus@0/:
  /proc/device-tree/bus@0/spi@3210000/  (SPI1, 40-pin header)
  /proc/device-tree/bus@0/spi@3230000/  (SPI3, internal)

Usage:  sudo python3 test_spi_diag.py
"""

import glob
import os
import subprocess

PASS = "\033[92m[OK]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
WARN = "\033[93m[WARN]\033[0m"
INFO = "\033[94m[INFO]\033[0m"

errors = 0
warnings = 0


def check(label, condition, hint=""):
    global errors, warnings
    if condition:
        print(f"  {PASS}  {label}")
    else:
        print(f"  {FAIL}  {label}")
        if hint:
            print(f"         -> {hint}")
        errors += 1


def warn(label, condition, hint=""):
    global warnings
    if condition:
        print(f"  {PASS}  {label}")
    else:
        print(f"  {WARN}  {label}")
        if hint:
            print(f"         -> {hint}")
        warnings += 1


def read_file(path):
    try:
        with open(path, "r") as f:
            return f.read().strip().rstrip("\x00")
    except (FileNotFoundError, PermissionError, OSError):
        return None


def run_cmd(cmd):
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip()
    except Exception:
        return ""


# ── Check 1: spidev device files ──────────────────────────────────────────────

print("\n[1] SPI device files")
spidev_devices = sorted(glob.glob("/dev/spidev*"))
if spidev_devices:
    for dev in spidev_devices:
        mode = oct(os.stat(dev).st_mode)[-3:] if os.path.exists(dev) else "?"
        print(f"  {INFO}  {dev} (mode {mode})")
else:
    print(f"  {FAIL}  No /dev/spidev* found")
    errors += 1

check(
    "At least one spidev device exists",
    len(spidev_devices) > 0,
    "Run: sudo /opt/nvidia/jetson-io/jetson-io.py -> enable SPI1 -> reboot",
)

# ── Check 2: SPI master sysfs — map spidev to spi@ address ────────────────────

print("\n[2] SPI master mapping (spidev -> spi@ address)")
spi_masters = sorted(glob.glob("/sys/class/spi_master/spi*"))
spi_mapping = {}

for master in spi_masters:
    master_name = os.path.basename(master)
    for child in os.listdir(master):
        if child.startswith("spi"):
            modalias = read_file(os.path.join(master, child, "modalias"))
            runtime = read_file(os.path.join(master, child, "power", "runtime_status"))
            # Try to resolve the symlinks to find the spi@ address
            driver_link = os.path.join(master, "driver")
            of_node = os.path.join(master, "of_node")
            of_path = None
            if os.path.islink(of_node):
                of_path = os.readlink(of_node)
            print(f"  {INFO}  {master_name}/{child}: modalias={modalias}, runtime={runtime}, of_node={of_path}")
            spi_mapping[child] = {
                "master": master_name,
                "modalias": modalias,
                "runtime": runtime,
                "of_node": of_path,
            }

# ── Check 3: Device tree — spi@ nodes under bus@0/ ───────────────────────────

print("\n[3] Device tree spi@ nodes (under bus@0/)")
dt_base = "/proc/device-tree/bus@0"
dt_spi_nodes = sorted(glob.glob(f"{dt_base}/spi@*"))
if not dt_spi_nodes:
    # Fallback: also check root level
    dt_spi_nodes = sorted(glob.glob("/proc/device-tree/spi@*"))
    if dt_spi_nodes:
        print(f"  {INFO}  Found at root level (not under bus@0/)")

spi_3210000_ok = False
for node in dt_spi_nodes:
    name = os.path.basename(node)
    status = read_file(os.path.join(node, "status"))
    children = sorted([d for d in os.listdir(node) if d.startswith("spi")])
    compatible = read_file(os.path.join(node, "compatible"))
    print(f"  {INFO}  {name}: status={status}, compatible={compatible}, children={children}")

    if name == "spi@3210000":
        label = "spi@3210000 (SPI1 40-pin header)"
        check(f"{label} status == okay", status == "okay", f"Got '{status}'. Run jetson-io to enable SPI1.")
        check(f"{label} has child nodes", len(children) > 0, "No spi@ child nodes — spidev won't be created.")
        if status == "okay" and len(children) > 0:
            spi_3210000_ok = True
            for child in children:
                child_status = read_file(os.path.join(node, child, "status"))
                child_compat = read_file(os.path.join(node, child, "compatible"))
                print(f"  {INFO}    {child}: status={child_status}, compatible={child_compat}")
    elif name == "spi@3230000":
        print(f"  {INFO}    ^ This is SPI3 (internal), NOT the 40-pin header SPI1")

if not dt_spi_nodes:
    check("Device tree spi@ nodes found", False, "No spi@ nodes in device tree — overlay not loaded?")

# ── Check 4: Pinmux — pinconf-groups ──────────────────────────────────────────

print("\n[4] Pinmux (pinconf-groups)")
# Find the pinctrl base path
pinctrl_dirs = glob.glob("/sys/kernel/debug/pinctrl/*")
pinmux_dirs = [d for d in pinctrl_dirs if "2430000" in d or "pinmux" in os.path.basename(d)]
if not pinmux_dirs:
    # Try to find any pinctrl directory
    pinmux_dirs = [d for d in pinctrl_dirs if os.path.isdir(d)]

pinconf_content = None
for d in pinmux_dirs:
    content = read_file(os.path.join(d, "pinconf-groups"))
    if content:
        pinconf_content = content
        print(f"  {INFO}  Reading from: {d}/pinconf-groups")
        break

if pinconf_content:
    # Look for SPI1-related pin groups
    lines = pinconf_content.splitlines()
    spi1_pins = []
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if "spi1" in line_lower or ("mosi" in line_lower and "pz5" in line_lower):
            # Grab this line and the next few lines (pin config)
            context = lines[max(0, i - 1):min(len(lines), i + 8)]
            spi1_pins.append("\n".join(context))

    if spi1_pins:
        print(f"  {INFO}  SPI1-related pin entries found:")
        for entry in spi1_pins:
            for line in entry.splitlines():
                print(f"         {line.strip()}")
        check("SPI1 pinmux entries found in pinconf-groups", True)
        # Check if function is spi1
        has_spi1_func = any("func=spi1" in p for p in spi1_pins)
        check("SPI1 pins configured with func=spi1", has_spi1_func,
              "Pins are not muxed to SPI1 function")
    else:
        # Also check for spi3 (might be the one on 40-pin)
        spi3_pins = []
        for i, line in enumerate(lines):
            if "spi3" in line.lower():
                context = lines[max(0, i - 1):min(len(lines), i + 8)]
                spi3_pins.append("\n".join(context))
        if spi3_pins:
            print(f"  {WARN}  Found SPI3 entries instead of SPI1:")
            for entry in spi3_pins:
                for line in entry.splitlines():
                    print(f"         {line.strip()}")
            check("SPI1 pinmux entries found in pinconf-groups", False,
                  "Only SPI3 found — SPI1 not configured in pinmux")
        else:
            check("SPI1 pinmux entries found in pinconf-groups", False,
                  "No spi1 or spi3 entries in pinconf-groups")
else:
    warn("Could not read pinconf-groups", False, "Run with sudo, or pinctrl debugfs not available")

# ── Check 5: GPIO allocation ──────────────────────────────────────────────────

print("\n[5] GPIO allocation (tegra_gpio)")
gpio_debug = run_cmd("sudo cat /sys/kernel/debug/gpio 2>/dev/null")
if gpio_debug:
    spi1_gpio = [line for line in gpio_debug.splitlines() if "SPI1" in line]
    spi3_gpio = [line for line in gpio_debug.splitlines() if "SPI3" in line]
    all_spi_gpio = [line for line in gpio_debug.splitlines() if "SPI" in line]

    if spi1_gpio:
        print(f"  {INFO}  SPI1 GPIO lines (correct for 40-pin header):")
        for line in spi1_gpio:
            print(f"         {line.strip()}")
        check("SPI1_MOSI allocated to SPI driver", any("SPI1_MOSI" in l for l in spi1_gpio))
    elif spi3_gpio:
        print(f"  {WARN}  SPI3 GPIO lines found (this is the internal SPI, not 40-pin header):")
        for line in spi3_gpio:
            print(f"         {line.strip()}")
        check("SPI1_MOSI allocated to SPI driver", False,
              "Only SPI3 GPIO found — SPI1 not configured")
    elif all_spi_gpio:
        print(f"  {INFO}  Other SPI GPIO lines:")
        for line in all_spi_gpio:
            print(f"         {line.strip()}")
        check("SPI1_MOSI allocated to SPI driver", False, "No SPI1 GPIO entries")
    else:
        warn("No SPI GPIO entries found", False, "GPIO debugfs may need sudo or is empty")
else:
    warn("Could not read tegra_gpio", False, "Run with sudo")

# ── Check 6: spidev Python open test — all devices ────────────────────────────

print("\n[6] spidev Python open test (all devices)")
try:
    import spidev

    for dev_path in spidev_devices:
        bus, cs = dev_path.replace("/dev/spidev", "").split(".")
        bus, cs = int(bus), int(cs)
        try:
            spi = spidev.SpiDev()
            spi.open(bus, cs)
            speed = spi.max_speed_hz
            mode = spi.mode
            bpw = spi.bits_per_word
            spi.close()
            print(f"  {PASS}  spidev{bus}.{cs}: speed={speed} Hz, mode={mode}, bpw={bpw}")
        except Exception as e:
            print(f"  {FAIL}  spidev{bus}.{cs}: {e}")
except ImportError:
    check("spidev module available", False, "Install: pip3 install spidev")

# ── Check 7: Write test — which spidev reaches Pin 19? ────────────────────────

print("\n[7] SPI write test — which spidev is SPI1_MOSI (Pin 19)?")
try:
    import spidev

    BIT0 = 0b11000000
    BIT1 = 0b11110000

    def encode_ws2812(r, g, b):
        data = bytearray(24)
        for byte_idx, val in enumerate((g, r, b)):
            for bit_idx in range(8):
                data[byte_idx * 8 + bit_idx] = BIT1 if val & (1 << (7 - bit_idx)) else BIT0
        return data

    frame = encode_ws2812(255, 0, 0) * 25
    frame += bytes(350)

    print(f"  {INFO}  Sending red frame ({len(frame)} bytes) to each spidev device...")
    print(f"  {INFO}  Watch the LEDs — the device that lights them red is the correct one.\n")

    for dev_path in spidev_devices:
        bus, cs = dev_path.replace("/dev/spidev", "").split(".")
        bus, cs = int(bus), int(cs)
        try:
            spi = spidev.SpiDev()
            spi.open(bus, cs)
            spi.max_speed_hz = 6400000
            spi.mode = 0b00
            spi.writebytes(list(frame))
            spi.close()
            print(f"  {INFO}  -> spidev{bus}.{cs}: writebytes OK (did LEDs light red?)")
        except Exception as e:
            print(f"  {FAIL}  -> spidev{bus}.{cs}: write failed: {e}")

    print(f"\n  {INFO}  If NONE of the devices lit the LEDs, the issue is likely:")
    print(f"  {INFO}    a) Pinmux not configured — SPI not routed to physical pins")
    print(f"  {INFO}    b) 3.3V logic level (WS2812B needs >= 3.5V, Jetson outputs 3.3V)")
    print(f"  {INFO}    c) Wrong wiring (check DIN on Pin 19, GND on Pin 6)")

except Exception as e:
    check(f"SPI write test failed: {e}", False)

# ── Check 8: Recommended spidev device ────────────────────────────────────────

print("\n[8] Recommendation")
has_spidev0 = any("spidev0" in d for d in spidev_devices)
dt_spi1_status = None
# Check both possible paths
for path in [
    "/proc/device-tree/bus@0/spi@3210000/status",
    "/proc/device-tree/spi@3210000/status",
]:
    dt_spi1_status = read_file(path)
    if dt_spi1_status is not None:
        break

if has_spidev0 and spi_3210000_ok:
    print(f"  {PASS}  Use spidev0.0 for WS2812B via SPI1_MOSI (Pin 19)")
    print(f"  {INFO}  In ws2812.py: SPI_DEVICE = 0, SPI_CHIP = 0")
elif has_spidev0:
    print(f"  {WARN}  spidev0.0 exists but spi@3210000 not confirmed okay")
    print(f"  {INFO}  spi@3210000 status = '{dt_spi1_status}'")
    print(f"  {INFO}  Device tree may need reconfiguration via jetson-io")
else:
    print(f"  {FAIL}  No spidev0 found — SPI1 not configured")
    print(f"  {INFO}  Run: sudo /opt/nvidia/jetson-io/jetson-io.py -> enable SPI1 -> reboot")

# ── Check 9: Device tree overlay status ────────────────────────────────────────

print("\n[9] Device tree overlay (jetson-io)")
# Check extlinux.conf for overlays
extlinux_conf = read_file("/boot/extlinux/extlinux.conf")
if extlinux_conf:
    has_overlays = "overlays=" in extlinux_conf
    print(f"  {INFO}  /boot/extlinux/extlinux.conf exists")
    if has_overlays:
        for line in extlinux_conf.splitlines():
            if "overlays=" in line:
                print(f"  {INFO}    {line.strip()}")
        check("Overlays directive found in extlinux.conf", True)
    else:
        print(f"  {WARN}  No 'overlays=' line in extlinux.conf")
        check("Overlays directive found in extlinux.conf", False,
              "jetson-io overlay may not be applied at boot")
else:
    check("/boot/extlinux/extlinux.conf exists", False, "File not found")

# Check for custom dtbo file
dtbo_files = glob.glob("/boot/*hdr40*custom*") + glob.glob("/boot/*user*custom*")
if dtbo_files:
    print(f"  {INFO}  Custom DTBO files found:")
    for f in dtbo_files:
        print(f"  {INFO}    {f}")
else:
    print(f"  {WARN}  No custom *hdr40* or *user* DTBO found in /boot/")
    print(f"  {INFO}  jetson-io typically creates: kernel_tegra234-*-hdr40-user-custom.dtbo")

# Check applied overlays
applied = run_cmd("sudo cat /sys/kernel/debug/dynamic_debug/debug 2>/dev/null")
# Alternative: check via /sys/firmware/devicetree
overlay_base = glob.glob("/sys/firmware/devicetree/base/fragment*")
if overlay_base:
    print(f"  {INFO}  Active device tree fragments: {len(overlay_base)}")
else:
    print(f"  {INFO}  No /sys/firmware/devicetree/base/fragment* found")

# ── Check 10: Live pinmux — pinctrl-pins ──────────────────────────────────────

print("\n[10] Live pinmux — pinctrl pin status")
# Check pinmux-pins for SPI1 related pins (GP49 = Pin 19)
pinmux_pins = run_cmd("sudo cat /sys/kernel/debug/pinctrl/*/pinmux-pins 2>/dev/null")
if not pinmux_pins:
    # Try alternative paths
    pinctrl_dirs = glob.glob("/sys/kernel/debug/pinctrl/*")
    for d in pinctrl_dirs:
        content = read_file(os.path.join(d, "pinmux-pins"))
        if content and "spi" in content.lower():
            pinmux_pins = content
            print(f"  {INFO}  Reading from: {d}/pinmux-pins")
            break

if pinmux_pins:
    # Look for pin 19 / GP49 / spi1_mosi
    lines = pinmux_pins.splitlines()
    relevant = []
    for line in lines:
        ll = line.lower()
        if any(kw in ll for kw in ["gp49", "spi1_mosi", "pz5", "pin 19"]):
            relevant.append(line)

    if relevant:
        print(f"  {INFO}  Pin 19 / GP49 / SPI1_MOSI entries:")
        for line in relevant:
            print(f"         {line.strip()}")
        check("Pin 19 is claimed by SPI driver",
              any("spi" in r.lower() for r in relevant),
              "Pin 19 may still be in GPIO mode — not routed to SPI")
    else:
        print(f"  {WARN}  No Pin 19 / GP49 / SPI1_MOSI entries found in pinmux-pins")
else:
    warn("Could not read pinmux-pins", False, "Run with sudo, or pinctrl debugfs not available")

# ── Summary ────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
if errors == 0:
    print(f"\033[92mAll checks passed\033[0m — SPI1 appears correctly configured.")
    if warnings:
        print(f"  ({warnings} warning(s) above)")
else:
    print(f"\033[91m{errors} check(s) failed\033[0m — SPI1 is NOT ready.")
    print("  Fix the issues above, then re-run this script.")
print()
