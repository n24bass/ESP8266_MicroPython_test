# MicroPython SSD1306 OLED driver, I2C and SPI interfaces

import time
import framebuf

# register definitions
SET_CONTRAST        = const(0x81)
SET_ENTIRE_ON       = const(0xa4)
SET_NORM_INV        = const(0xa6)
SET_DISP            = const(0xae)
SET_MEM_ADDR        = const(0x20)
SET_COL_ADDR        = const(0x21)
SET_PAGE_ADDR       = const(0x22)
SET_DISP_START_LINE = const(0x40)
SET_SEG_REMAP       = const(0xa0)
SET_MUX_RATIO       = const(0xa8)
SET_COM_OUT_DIR     = const(0xc0)
SET_DISP_OFFSET     = const(0xd3)
SET_COM_PIN_CFG     = const(0xda)
SET_DISP_CLK_DIV    = const(0xd5)
SET_PRECHARGE       = const(0xd9)
SET_VCOM_DESEL      = const(0xdb)
SET_CHARGE_PUMP     = const(0x8d)


class SSD1306:
    def __init__(self, width, height, external_vcc):
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.pages = self.height // 8
        # Note the subclass must initialize self.framebuf to a framebuffer.
        # This is necessary because the underlying data buffer is different
        # between I2C and SPI implementations (I2C needs an extra byte).
        self.poweron()
        self.init_display()

    def init_display(self):
        for cmd in (
            SET_DISP | 0x00, # off
            # address setting
            SET_MEM_ADDR, 0x00, # horizontal
            # resolution and layout
            SET_DISP_START_LINE | 0x00,
            SET_SEG_REMAP | 0x01, # column addr 127 mapped to SEG0
            SET_MUX_RATIO, self.height - 1,
            SET_COM_OUT_DIR | 0x08, # scan from COM[N] to COM0
            SET_DISP_OFFSET, 0x00,
            SET_COM_PIN_CFG, 0x02 if self.height == 32 else 0x12,
            # timing and driving scheme
            SET_DISP_CLK_DIV, 0x80,
            SET_PRECHARGE, 0x22 if self.external_vcc else 0xf1,
            SET_VCOM_DESEL, 0x30, # 0.83*Vcc
            # display
            SET_CONTRAST, 0xff, # maximum
            SET_ENTIRE_ON, # output follows RAM contents
            SET_NORM_INV, # not inverted
            # charge pump
            SET_CHARGE_PUMP, 0x10 if self.external_vcc else 0x14,
            SET_DISP | 0x01): # on
            self.write_cmd(cmd)
        self.fill(0)
        self.show()

    def poweroff(self):
        self.write_cmd(SET_DISP | 0x00)

    def contrast(self, contrast):
        self.write_cmd(SET_CONTRAST)
        self.write_cmd(contrast)

    def invert(self, invert):
        self.write_cmd(SET_NORM_INV | (invert & 1))

    def show(self):
        x0 = 0
        x1 = self.width - 1
        if self.width == 64:
            # displays with width of 64 pixels are shifted by 32
            x0 += 32
            x1 += 32
        self.write_cmd(SET_COL_ADDR)
        self.write_cmd(x0)
        self.write_cmd(x1)
        self.write_cmd(SET_PAGE_ADDR)
        self.write_cmd(0)
        self.write_cmd(self.pages - 1)
        self.write_framebuf()

    def fill(self, col):
        self.framebuf.fill(col)

    def pixel(self, x, y, col):
        self.framebuf.pixel(x, y, col)

    def scroll(self, dx, dy):
        self.framebuf.scroll(dx, dy)

    def text(self, string, x, y, col=1):
        self.framebuf.text(string, x, y, col)


class SSD1306_I2C(SSD1306):
    def __init__(self, width, height, i2c, addr=0x3c, external_vcc=False):
        self.i2c = i2c
        self.addr = addr
        self.temp = bytearray(2)
        # Add an extra byte to the data buffer to hold an I2C data/command byte
        # to use hardware-compatible I2C transactions.  A memoryview of the
        # buffer is used to mask this byte from the framebuffer operations
        # (without a major memory hit as memoryview doesn't copy to a separate
        # buffer).
        self.buffer = bytearray(((height // 8) * width) + 1)
        self.buffer[0] = 0x40  # Set first byte of data buffer to Co=0, D/C=1
        self.framebuf = framebuf.FrameBuffer1(memoryview(self.buffer)[1:], width, height)
        super().__init__(width, height, external_vcc)

    def write_cmd(self, cmd):
        self.temp[0] = 0x80 # Co=1, D/C#=0
        self.temp[1] = cmd
        self.i2c.writeto(self.addr, self.temp)

    def write_framebuf(self):
        # Blast out the frame buffer using a single I2C transaction to support
        # hardware I2C interfaces.
        self.i2c.writeto(self.addr, self.buffer)

    def poweron(self):
        pass


class SSD1306_SPI(SSD1306):
    def __init__(self, width, height, spi, dc, res, cs, cs2, external_vcc=False):
        self.rate = 10 * 1024 * 1024
        dc.init(dc.OUT, value=0)
        res.init(res.OUT, value=0)
        cs.init(cs.OUT, value=1)
        cs2.init(cs2.OUT, value=1) # chip select for KANJI
        self.spi = spi
        self.dc = dc
        self.res = res
        self.cs = cs
        self.cs2 = cs2
        self.buffer = bytearray((height // 8) * width)
        self.framebuf = framebuf.FrameBuffer1(self.buffer, width, height)
        self.matrixdata = bytearray([0 for i in range(32)])
        super().__init__(width, height, external_vcc)

    def write_cmd(self, cmd):
        self.spi.init(baudrate=self.rate, polarity=0, phase=0)
        self.cs.high()
        self.dc.low()
        self.cs.low()
        self.spi.write(bytearray([cmd]))
        self.cs.high()

    def write_framebuf(self):
        self.spi.init(baudrate=self.rate, polarity=0, phase=0)
        self.cs.high()
        self.dc.high()
        self.cs.low()
        self.spi.write(self.buffer)
        self.cs.high()

    def poweron(self):
        self.res.high()
        time.sleep_ms(1)
        self.res.low()
        time.sleep_ms(10)
        self.res.high()

    def read_kanji(self, code):
        # print(code)
        c1 = code>>8
        c2 = code & 0xFF
        seq = (c1-129 if c1<=159 else c1-193)*188 + (c2-64 if c2<=126 else c2-65)
        MSB = int(seq / 94 + 1)
        LSB = seq % 94 + 1
        Address = 0
        
        if MSB >=  1 and MSB <= 15 and LSB >= 1 and LSB <= 94:
            Address =( (MSB -  1) * 94 + (LSB - 1))*32
        elif MSB >= 16 and MSB <= 47 and LSB >= 1 and LSB <= 94:
            Address =( (MSB - 16) * 94 + (LSB - 1))*32 + 0x0AA40
        elif MSB >= 48 and MSB <= 84 and LSB >= 1 and LSB <= 94:
            Address = ((MSB - 48) * 94 + (LSB - 1))*32 + 0x21CDF
        elif MSB == 85 and                LSB >= 1 and LSB <= 94:
            Address = ((MSB - 85) * 94 + (LSB - 1))*32 + 0x3C4A0
        elif MSB >= 88 and MSB <= 89 and LSB >= 1 and LSB <= 94:
            Address = ((MSB - 88) * 94 + (LSB - 1))*32 + 0x3D060
        Address = int(Address)
         
        self.cs2.low() # Select the device by seting chip select low
        self.spi.write(bytearray([0x03, (Address>>16) & 0xff, (Address>>8) & 0xff, Address & 0xff]))
         
        # send a dummy byte to receive the contents of the WHOAMI register
        self.matrixdata = bytearray(self.spi.read(32, 0x00))
        self.cs2.high() # deselect the device

    def draw_kanji(self, offset_x, offset_y):
        for x in range(0, 32): # int x=0; x<32; x++)
            for y in range(0, 8): 
                color = 1 if self.matrixdata[x] & (1<<y) else 0
                self.framebuf.pixel(x % 16 + offset_x, y+(8*(x>>4)) + offset_y, color)
        
    def put_kanji(self, offset_x, offset_y, c):
        self.read_kanji(c)
        self.draw_kanji(offset_x, offset_y)
        # self.show() # lcd.copy_to_lcd()

    def test(self):
        for x in range(0, 32):
            self.framebuf.pixel(x, x, 1)
        self.show()
