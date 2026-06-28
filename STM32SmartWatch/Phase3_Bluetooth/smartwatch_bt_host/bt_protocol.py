"""
HC-05 Bluetooth frame protocol for STM32 SmartWatch Phase 3.

Frame format:
    [STX(0xAA)] [CMD(1B)] [LEN(1B)] [DATA(LEN)] [CHK(1B)] [ETX(0x55)]

CHK = CMD ^ LEN ^ DATA[0] ^ ... ^ DATA[N-1]
"""

import struct

# -------- Frame constants --------
BT_STX = 0xAA
BT_ETX = 0x55

BT_CMD_SENSOR_DATA = 0x01
BT_CMD_TIME_SYNC   = 0x02
BT_CMD_ACK         = 0x03

BT_RX_BUF_SIZE = 256
BT_TX_BUF_SIZE = 256

# -------- HC-05 default settings --------
HC05_DEFAULTS = {
    "name":     "HC-05",
    "baudrate": 38400,
    "password": "none (部分模块为 1234)",
    "role":     "Slave",
    "mode":     "Data (Normal)",
}

STM32_PINS = {
    "TX":  "PA2 (USART2_TX -> HC-05 RXD)",
    "RX":  "PA3 (USART2_RX -> HC-05 TXD)",
    "STATE": "PB0 (HC-05 STATE, HIGH=connected)",
}


class FrameParser:
    """Parse incoming byte stream into complete frames."""

    def __init__(self):
        self._buf = bytearray()
        self._state = 0       # 0=waiting STX, 1=CMD, 2=LEN, 3=DATA, 4=CHK, 5=ETX
        self._cmd = 0
        self._len = 0
        self._data = bytearray()
        self._chk = 0

    def feed(self, chunk: bytes) -> list[tuple[int, bytes]]:
        """Feed raw bytes, return list of (cmd, data) for each complete valid frame."""
        frames = []
        for b in chunk:
            if self._state == 0:
                if b == BT_STX:
                    self._state = 1
            elif self._state == 1:
                self._cmd = b
                self._state = 2
            elif self._state == 2:
                self._len = b
                self._data = bytearray()
                self._state = 3
            elif self._state == 3:
                self._data.append(b)
                if len(self._data) >= self._len:
                    self._state = 4
            elif self._state == 4:
                self._chk = b
                self._state = 5
            elif self._state == 5:
                self._state = 0
                if b == BT_ETX:
                    chk = self._cmd ^ self._len
                    for d in self._data:
                        chk ^= d
                    if chk == self._chk:
                        frames.append((self._cmd, bytes(self._data)))
        return frames


def parse_sensor_data(data: bytes) -> dict:
    """Parse 24-byte sensor data payload into accelerometer and gyroscope values."""
    if len(data) != 24:
        raise ValueError(f"Expected 24 bytes, got {len(data)}")
    ax, ay, az, gx, gy, gz = struct.unpack("<ffffff", data)
    return {
        "ax": ax, "ay": ay, "az": az,
        "gx": gx, "gy": gy, "gz": gz,
    }


def build_time_sync_cmd(hour: int, minute: int, second: int,
                         year: int, month: int, day: int) -> bytes:
    """Build a CMD_TIME_SYNC frame to send to the watch."""
    data = bytearray(7)
    data[0] = hour
    data[1] = minute
    data[2] = second
    data[3] = (year >> 8) & 0xFF
    data[4] = year & 0xFF
    data[5] = month
    data[6] = day

    chk = BT_CMD_TIME_SYNC ^ 7
    for b in data:
        chk ^= b

    frame = bytearray(5 + len(data))
    frame[0] = BT_STX
    frame[1] = BT_CMD_TIME_SYNC
    frame[2] = len(data)
    frame[3:3+len(data)] = data
    frame[3+len(data)] = chk
    frame[4+len(data)] = BT_ETX
    return bytes(frame)
