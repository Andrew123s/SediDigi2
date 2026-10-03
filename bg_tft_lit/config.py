import Jetson.GPIO as GPIO
import logging
import time
import spidev
import os

RST_PIN  = 31
DC_PIN   = 29
CS_PIN   = 24
BL_PIN   = 15

PWM_CHIP = 0
PWM_CHANNEL = 0
PWM_PERIOD_NS = 50_000   # 20 kHz (was 100_000 = 10 kHz)

spi = spidev.SpiDev(0, 0)

def delay_ms(delaytime):
    time.sleep(delaytime / 1000.0)

def spi_writebyte(data):
    spi.writebytes([data])

def spi_writebytes(data):
    for i in range(0, len(data), 4096):
        spi.writebytes(data[i:i+4096])

def module_init():
    GPIO.setmode(GPIO.BOARD)
    GPIO.setwarnings(False)
    GPIO.setup(RST_PIN, GPIO.OUT)
    GPIO.setup(DC_PIN, GPIO.OUT)
    GPIO.setup(CS_PIN, GPIO.OUT)
    GPIO.output(RST_PIN, 0)
    GPIO.output(CS_PIN, 0)
    GPIO.output(DC_PIN, 0)
    spi.max_speed_hz = 20000000
    spi.mode = 0b00
    return 0

def module_exit():
    pwm_exit()
    spi.close()
    GPIO.output(RST_PIN, 0)
    GPIO.output(DC_PIN, 0)
    GPIO.cleanup()

def _pwm_sysfs_path():
    return f"/sys/class/pwm/pwmchip{PWM_CHIP}/pwm{PWM_CHANNEL}"

def pwm_init(brightness_percent=100):
    pwm_path = _pwm_sysfs_path()
    export_path = f"/sys/class/pwm/pwmchip{PWM_CHIP}/export"
    if not os.path.isdir(pwm_path):
        try:
            with open(export_path, "w") as f:
                f.write(str(PWM_CHANNEL))
            time.sleep(0.1)
        except (PermissionError, IOError, OSError) as e:
            logging.error(f"Cannot export PWM: {e}")
            return -1
    try:
        with open(f"{pwm_path}/period", "w") as f:
            f.write(str(PWM_PERIOD_NS))
        pwm_set_brightness(brightness_percent)
        with open(f"{pwm_path}/enable", "w") as f:
            f.write("1")
    except (PermissionError, IOError, OSError) as e:
        logging.error(f"Cannot configure PWM: {e}")
        return -1
    return 0

def pwm_set_brightness(percent):
    percent = max(0, min(100, percent))
    duty = int(PWM_PERIOD_NS * percent / 100)
    pwm_path = _pwm_sysfs_path()
    if not os.path.isdir(pwm_path):
        return
    try:
        with open(f"{pwm_path}/duty_cycle", "w") as f:
            f.write(str(duty))
    except (PermissionError, IOError, OSError):
        pass

def pwm_exit():
    pwm_path = _pwm_sysfs_path()
    if not os.path.isdir(pwm_path):
        return
    try:
        with open(f"{pwm_path}/duty_cycle", "w") as f:
            f.write("0")
    except (PermissionError, IOError, OSError):
        pass
    try:
        with open(f"{pwm_path}/enable", "w") as f:
            f.write("0")
    except (PermissionError, IOError, OSError):
        pass
    try:
        with open(f"/sys/class/pwm/pwmchip{PWM_CHIP}/unexport", "w") as f:
            f.write(str(PWM_CHANNEL))
    except (PermissionError, IOError, OSError):
        pass
