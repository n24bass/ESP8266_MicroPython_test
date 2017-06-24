# https://learn.adafruit.com/micropython-hardware-ssd1306-oled-display/software
#
# SPI
# SPI1=HSPI GPIO12(6):MISO,GPIO13(D7):MOSI,GPIO14(D5):CLK
# GPIO15(D8):dc, GPIO0(D3):rst, GPIO16(D0):cs
import machine
spi = machine.SPI(1, baudrate=8000000, polarity=0, phase=0)
import ssd1306j
oled = ssd1306j.SSD1306_SPI(128, 64, spi, machine.Pin(15), machine.Pin(0), machine.Pin(16), machine.Pin(5))
# oled = ssd1306.SSD1306_SPI(128, 64, spi, machine.Pin(15), machine.Pin(0), machine.Pin(16))
# oled = ssd1306.SSD1306_SPI(128, 64, spi, machine.Pin(15), machine.Pin(0), machine.Pin(16))

# I2C
# import machine
# i2c = machine.I2C(machine.Pin(2), machine.Pin(0))
# import ssd1306
# oled = ssd1306.SSD1306_I2C(128, 64, i2c)

oled.fill(1)
oled.show()

oled.fill(0)
oled.text('Hello, world!', 0, 0)
oled.show()

x = 0
y = 10
for c in [0x93fa, 0x967b, 0x8cea, 0x955c, 0x8ea6]:
    oled.put_kanji(x, y, c)
    x += 16
oled.show()
