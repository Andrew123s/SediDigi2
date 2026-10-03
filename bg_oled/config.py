import Jetson.GPIO as GPIO
import time
import spidev

RST_PIN = 31
DC_PIN  = 29
CS_PIN  = 24

Device_SPI = 1
Device_I2C = 0

if Device_SPI == 1:
    Device = Device_SPI
    spi = spidev.SpiDev(0, 0)
else:
    Device = Device_I2C
    import smbus
    address = 0x3c
    bus = smbus.SMBus(1)

def delay_ms(delaytime):
    time.sleep(delaytime / 1000.0)

def spi_writebyte(data):
    spi.writebytes([data[0]])

def spi_write(data):
    chunk_size = 4096
    for i in range(0, len(data), chunk_size):
        spi.writebytes(data[i:i + chunk_size])

def module_init():
    GPIO.setmode(GPIO.BOARD)
    GPIO.setwarnings(False)
    GPIO.setup(RST_PIN, GPIO.OUT)
    GPIO.setup(DC_PIN, GPIO.OUT)
    GPIO.setup(CS_PIN, GPIO.OUT)
    GPIO.output(RST_PIN, 0)
    if Device == Device_SPI:
        spi.max_speed_hz = 10000000
        spi.mode = 0b11
    GPIO.output(CS_PIN, 0)
    GPIO.output(DC_PIN, 0)
    return 0

def module_exit():
    if Device == Device_SPI:
        spi.close()
    GPIO.output(RST_PIN, 0)
    GPIO.output(DC_PIN, 0)
