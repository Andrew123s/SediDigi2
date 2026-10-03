import Jetson.GPIO as GPIO
import time
import spidev

RST_PIN  = 31
DC_PIN   = 29
CS_PIN   = 24

# SPI bus 0, chip select 0
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
    # Target SPI clock: 8 MHz (manufacturer limit for ST7735S)
    spi.max_speed_hz = 8000000
    # SPI mode 0: CPOL=0 (idle LOW), CPHA=0 (sample on rising edge)
    spi.mode = 0b00
    return 0

def module_exit():
    spi.close()
    GPIO.output(RST_PIN, 0)
    GPIO.output(DC_PIN, 0)
    GPIO.cleanup()
