import serial
import sliplib
import time
from pprint import pp
import sys

boot_time = time.monotonic()


def elapsed():
    return time.monotonic() - boot_time


class TestClient:
    def __init__(self):
        print(f"{elapsed()} opening port")
        self.__ser = serial.Serial(sys.argv[1], 115200, timeout=0.1)
        # time.sleep(2)
        self.__driver = sliplib.Driver()
        self.rx_msg_list = []

    def __serial_write(self, data: bytearray) -> None:
        print(f"{elapsed()} sending: {data.hex()}")
        self.__ser.write(data)

    def __receive(self):
        if len(self.rx_msg_list) == 0:
            sys.stderr.write("[")
            sys.stderr.flush()
            # block until timeout if nothing available, return as soon as anything arrives
            data = self.__ser.read(1)
            # if more bytes are available, grab them now
            if self.__ser.in_waiting > 0:
                data = data + self.__ser.read(self.__ser.in_waiting)
            if len(data) > 0:
                print(f"{elapsed()} received: {repr(data)}")
            sys.stderr.write("]")
            sys.stderr.flush()
            if len(data) > 0:
                self.rx_msg_list.extend(self.__driver.receive(data))

        if len(self.rx_msg_list) > 0:
            msg = self.rx_msg_list.pop(0)  # FIFO
            print(f"{elapsed()} popping msg: {msg}")
            return msg

        return None

    def __send(self, msg):
        data = self.__driver.send(bytes(msg))
        self.__serial_write(data)

    def wait_for(self, code, payload=None):
        start_time = time.monotonic()
        while time.monotonic() - start_time < 5:
            msg = self.__receive()
            if msg and len(msg) > 40:
                raise MemoryError
            if msg and msg[0] == code and (payload is None or msg[1:] == payload):
                return msg
        raise TimeoutError

    def test(self) -> None:
        last_init_time = 0
        init_tries = 0
        while True:
            if time.monotonic() - last_init_time > 1:
                if init_tries > 3:
                    raise TimeoutError
                last_init_time = time.monotonic()
                init_tries += 1
                self.__send(b"\x03")
            msg = self.__receive()
            if msg and msg[0] == 0xC3:
                break
        self.__send(b"\x05\x00\xff")
        self.wait_for(0xC5)
        self.__send(b"\x04")
        self.wait_for(0xC4)
        self.__send(b"\x26")
        self.wait_for(0xEE)
        self.__send(b"\x25")
        self.wait_for(0xEE, b"help\n")

        print("TEST DONE")


TestClient().test()
