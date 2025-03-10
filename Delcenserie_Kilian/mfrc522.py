from machine import Pin, SPI
from time import sleep_ms

class MFRC522:

    OK = 0
    NOTAGERR = 1
    ERR = 2

    REQIDL = 0x26
    REQALL = 0x52
    AUTHENT1A = 0x60
    AUTHENT1B = 0x61

    def __init__(self, spi, cs, rst):
        self.spi = spi
        self.cs = Pin(cs, Pin.OUT)
        self.rst = Pin(rst, Pin.OUT)

        self.cs.value(1)
        self.rst.value(0)
        self.rst.value(1)

        self.init()

    def _wreg(self, reg, val):
        self.cs.value(0)
        self.spi.write(bytearray([(reg << 1) & 0x7E]))
        self.spi.write(bytearray([val]))
        self.cs.value(1)

    def _rreg(self, reg):
        self.cs.value(0)
        self.spi.write(bytearray([((reg << 1) & 0x7E) | 0x80]))
        val = self.spi.read(1)
        self.cs.value(1)
        return val[0]

    def _sbits(self, reg, mask):
        self._wreg(reg, self._rreg(reg) | mask)

    def _cbits(self, reg, mask):
        self._wreg(reg, self._rreg(reg) & (~mask))

    def _tocard(self, cmd, send):
        recv = []
        bits = irq_en = wait_irq = n = 0
        stat = self.ERR

        if cmd == 0x0E:
            irq_en = 0x12
            wait_irq = 0x10
        if cmd == 0x0C:
            irq_en = 0x77
            wait_irq = 0x30

        self._wreg(0x02, irq_en | 0x80)
        self._cbits(0x04, 0x80)
        self._sbits(0x0A, 0x80)
        self._wreg(0x01, 0x00)

        for c in send:
            self._wreg(0x09, c)

        self._wreg(0x01, cmd)

        if cmd == 0x0C:
            self._sbits(0x0D, 0x80)

        i = 2000
        while True:
            n = self._rreg(0x04)
            i -= 1
            if ~((i != 0) and ~(n & 0x01) and ~(n & wait_irq)):
                break

        self._cbits(0x0D, 0x80)

        if i != 0:
            if (self._rreg(0x06) & 0x1B) == 0x00:
                stat = self.OK

                if n & irq_en & 0x01:
                    stat = self.NOTAGERR
                if cmd == 0x0C:
                    n = self._rreg(0x0A)
                    lbits = self._rreg(0x0C) & 0x07
                    if lbits != 0:
                        bits = (n - 1) * 8 + lbits
                    else:
                        bits = n * 8

                    if n == 0:
                        n = 1
                    if n > 16:
                        n = 16

                    for _ in range(n):
                        recv.append(self._rreg(0x09))
            else:
                stat = self.ERR

        return stat, recv, bits

    def _crc(self, data):
        self._wreg(0x05, 0x04)
        self._sbits(0x0A, 0x80)

        for c in data:
            self._wreg(0x09, c)

        self._wreg(0x01, 0x03)

        i = 0xFF
        while True:
            n = self._rreg(0x05)
            i -= 1
            if not ((i != 0) and not (n & 0x04)):
                break

        return [self._rreg(0x22), self._rreg(0x21)]

    def init(self):
        self.reset()
        self._wreg(0x2A, 0x8D)
        self._wreg(0x2B, 0x3E)
        self._wreg(0x2D, 30)
        self._wreg(0x2C, 0)
        self._wreg(0x15, 0x40)
        self._wreg(0x11, 0x3D)
        self.antenna_on()

    def reset(self):
        self._wreg(0x01, 0x0F)

    def antenna_on(self):
        if ~(self._rreg(0x14) & 0x03):
            self._sbits(0x14, 0x03)

    def antenna_off(self):
        self._cbits(0x14, 0x03)

    def request(self, mode):
        self._wreg(0x0D, 0x07)
        (stat, recv, bits) = self._tocard(0x0C, [mode])
        if (stat != self.OK) | (bits != 0x10):
            stat = self.ERR
        return stat, bits

    def anticoll(self):
        ser_chk = 0
        ser = [0x93, 0x20]
        self._wreg(0x0D, 0x00)
        (stat, recv, bits) = self._tocard(0x0C, ser)
        if stat == self.OK:
            if len(recv) == 5:
                for i in range(4):
                    ser_chk ^= recv[i]
                if ser_chk != recv[4]:
                    stat = self.ERR
            else:
                stat = self.ERR
        return stat, recv
