# epd1in54.py
# ePaper driver for MicroPython
# 2017.10 n24bass@gmail.com

from micropython import const
import framebuf
import time

# Display resolution
EPD_WIDTH = const(200)
EPD_HEIGHT = const(200)

# EPD1IN54 commands
DRIVER_OUTPUT_CONTROL                = const(0x01)
BOOSTER_SOFT_START_CONTROL           = const(0x0C)
GATE_SCAN_START_POSITION             = const(0x0F)
DEEP_SLEEP_MODE                      = const(0x10)
DATA_ENTRY_MODE_SETTING              = const(0x11)
SW_RESET                             = const(0x12)
TEMPERATURE_SENSOR_CONTROL           = const(0x1A)
MASTER_ACTIVATION                    = const(0x20)
DISPLAY_UPDATE_CONTROL_1             = const(0x21)
DISPLAY_UPDATE_CONTROL_2             = const(0x22)
WRITE_RAM                            = const(0x24)
WRITE_VCOM_REGISTER                  = const(0x2C)
WRITE_LUT_REGISTER                   = const(0x32)
SET_DUMMY_LINE_PERIOD                = const(0x3A)
SET_GATE_TIME                        = const(0x3B)
BORDER_WAVEFORM_CONTROL              = const(0x3C)
SET_RAM_X_ADDRESS_START_END_POSITION = const(0x44)
SET_RAM_Y_ADDRESS_START_END_POSITION = const(0x45)
SET_RAM_X_ADDRESS_COUNTER            = const(0x4E)
SET_RAM_Y_ADDRESS_COUNTER            = const(0x4F)
TERMINATE_FRAME_READ_WRITE           = const(0xFF)

LUT_FULL_UPDATE = bytes([
    0x02, 0x02, 0x01, 0x11, 0x12, 0x12, 0x22, 0x22, 
    0x66, 0x69, 0x69, 0x59, 0x58, 0x99, 0x99, 0x88, 
    0x00, 0x00, 0x00, 0x00, 0xF8, 0xB4, 0x13, 0x51, 
    0x35, 0x51, 0x51, 0x19, 0x01, 0x00
])

LUT_PARTIAL_UPDATE = bytes([
    0x10, 0x18, 0x18, 0x08, 0x18, 0x18, 0x08, 0x00, 
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 
    0x00, 0x00, 0x00, 0x00, 0x13, 0x14, 0x44, 0x12, 
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00
])

#      ESP8266
# BUSY D2 GPIO4
# RST  D4 GPIO2
# DC   D3 GPIO0
# CS   D8 GPIO15
# CLK  D5 GPIO14 
# DO   D6 GPIO12(not used)
# DIN  D7 BPIO13


class EPD:

    def __init__(self, spi, dc, res, cs, busy):
        # SPI
        self.rate = 2 * 1024 * 1024 # 2MHz
        self.spi = spi
        # other pin
        self.dc_pin = dc
        self.reset_pin = res
        self.cs_pin = cs
        self.busy_pin = busy

        # 
        self.width = EPD_WIDTH
        self.height = EPD_HEIGHT

        # frame buffer
        self.buffer = bytearray(EPD_HEIGHT * EPD_WIDTH // 8)
        fb = framebuf.FrameBuffer(self.buffer, self.width, self.height, framebuf.MONO_HLSB)
        self.framebuf = fb
        self.fill = fb.fill
        self.pixel = fb.pixel
        self.hline = fb.hline
        self.vline = fb.vline
        self.line = fb.line
        self.rect = fb.rect
        self.fill_rect = fb.fill_rect
        self.text = fb.text
        self.scroll = fb.scroll
        self.blit = fb.blit

        self.init_display()

    def init_display(self):
        self.dc_pin.init(self.dc_pin.OUT, value=0)
        self.reset_pin.init(self.reset_pin.OUT, value=0)
        self.cs_pin.init(self.cs_pin.OUT, value=1)
        self.busy_pin.init(self.busy_pin.IN)

        self.lut = LUT_FULL_UPDATE
        self.reset()

        self.send_command(DRIVER_OUTPUT_CONTROL)
        self.send_data(bytes([(EPD_HEIGHT - 1) & 0xFF, ((EPD_HEIGHT - 1) >> 8) & 0xFF, 0x00]))

        self.send_command(BOOSTER_SOFT_START_CONTROL)
        self.send_data(bytes([0xD7, 0xD6, 0x9D]))

        self.send_command(WRITE_VCOM_REGISTER)
        self.send_data(bytes([0xA8]))        # VCOM 7C

        self.send_command(SET_DUMMY_LINE_PERIOD)
        self.send_data(bytes([0x1A]))                    # 4 dummy lines per gate
        
        self.send_command(SET_GATE_TIME)
        self.send_data(bytes([0x08]))                    # 2us per line

        self.send_command(DATA_ENTRY_MODE_SETTING)
        self.send_data(bytes([0x03]))                    # X increment; Y increment
        
        self.set_lut(self.lut) # set LUT for full or partial update


    def send_command(self, command):
        self.spi.init(baudrate=self.rate, polarity=0, phase=0)
        self.cs_pin(1)
        self.dc_pin(0)
        self.cs_pin(0)
        self.spi.write(bytes([command]))
        self.cs_pin(1)

    def send_data(self, buf):
        self.spi.init(baudrate=self.rate, polarity=0, phase=0)
        self.cs_pin(1)
        self.dc_pin(1)
        self.cs_pin(0)
        self.spi.write(buf)
        self.cs_pin(1)

    def wait_until_idle(self):
        while (self.busy_pin() == 1):
            time.sleep_ms(100)

    def reset(self):
        self.reset_pin(0)
        time.sleep_ms(200)
        self.reset_pin(1)
        time.sleep_ms(200)

    def set_lut(self, lut):
        self.lut = lut
        self.send_command(WRITE_LUT_REGISTER)
        self.send_data(self.lut)

    def show(self):
        self.set_frame_memory()
        self.display_frame()
        
    def set_frame_memory(self):
        self.set_memory_area(0, 0, self.width - 1, self.height - 1)
        self.set_memory_pointer(0, 0)

        self.send_command(WRITE_RAM)
        self.send_data(self.buffer)

    def display_frame(self):
        self.send_command(DISPLAY_UPDATE_CONTROL_2)
        self.send_data(bytes([0xC4]))

        self.send_command(MASTER_ACTIVATION)
        self.send_command(TERMINATE_FRAME_READ_WRITE)

        self.wait_until_idle() # busy wait

    def set_memory_area(self, x_start=0, y_start=0, x_end=EPD_WIDTH-1, y_end=EPD_HEIGHT-1):
        # x point must be the multiple of 8 or the last 3 bits will be
        self.send_command(SET_RAM_X_ADDRESS_START_END_POSITION)
        self.send_data(bytes([(x_start >> 3) & 0xFF, (x_end >> 3) & 0xFF]))

        self.send_command(SET_RAM_Y_ADDRESS_START_END_POSITION)
        self.send_data(bytes([y_start & 0xFF, (y_start >> 8) & 0xFF, y_end & 0xFF, (y_end >> 8) & 0xFF]))

    def set_memory_pointer(self, x, y):
        # x point must be the multiple of 8 or the last 3 bits will be ignored 
        self.send_command(SET_RAM_X_ADDRESS_COUNTER)
        self.send_data(bytes([(x >> 3) & 0xFF]))

        self.send_command(SET_RAM_Y_ADDRESS_COUNTER)
        self.send_data(bytes([y & 0xFF, (y >> 8) & 0xFF]))

        self.wait_until_idle()

    def sleep(self):
        self.send_command(DEEP_SLEEP_MODE)
        self.wait_until_idle()

if __name__ == "__main__":
    from machine import Pin, SPI

    spi = SPI(1)
    epd = EPD(spi, dc=Pin(0), res=Pin(2), cs=Pin(15), busy=Pin(4))
    epd.fill(0)
    epd.text('ESP8266', 0, 0)
    epd.text('Waveshare ePaper', 0, 10)
    epd.show()
    
