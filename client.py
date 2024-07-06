import serial
import sliplib
import time
from pprint import pp


class TestClient:
    def __init__(self):
        self.__ser = serial.Serial(
            "/dev/tty.usbmodem64E8335F52DC2", 115200, timeout=0.1
        )
        time.sleep(2)
        self.__driver = sliplib.Driver()

    def __serial_write(self, data: bytearray) -> None:
        print(f"WRITING: {data.hex()}")
        self.__ser.write(data)

    def __serial_read(self, length: int) -> bytes:
        data = self.__ser.read(length)
        print(f"READING: {data.hex()}")
        return data

    def __receive(self):
        data = self.__serial_read(1000)
        if len(data) > 0:
            msg = self.__driver.receive(data)
            pp(msg)
            return msg
        return None

    def test(self) -> None:
        self.__serial_write(bytes.fromhex("c003c0"))
        msg = None
        while msg is None:
            print(".")
            msg = self.__receive()


TestClient().test()
