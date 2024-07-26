import sys

sys.stderr.write("hello\n")


class Tokens:
    reqStart = 0x01
    cnfStart = 0xC1
    reqLine = 0x82
    cnfLine = 0x42
    reqInfo = 0x03
    cnfInfo = 0xC3
    reqTest = 0x04
    cnfTest = 0xC4
    indState = 0x84
    helpCmd = 0x25
    sendCmd = 0x26
    beepCmd = 0x27
    setSingleCmd = 0x28
    setAllCmd = 0x29
    readEOLsensorsCmd = 0x2A
    readEncodersCmd = 0x2B
    autoReadCmd = 0x2C
    autoTestCmd = 0x2D
    stopCmd = 0x2E
    quitCmd = 0x2F
    reqInit = 0x05
    cnfInit = 0xC5
    testRes = 0xEE
    debug = 0x9F


def send(msg):
    sys.stdout.buffer.write(msg + b"\xc0")
    sys.stdout.flush()


msg = bytearray()
while True:
    data = sys.stdin.buffer.read(1)
    if len(data) < 1:
        break
    b = data[0]
    sys.stderr.write(f"> {data.hex()}\n")
    if b == 0xC0:
        if len(msg) < 1:
            pass
        elif msg[0] == Tokens.reqInfo:
            payload = bytearray(22)
            payload[0] = Tokens.cnfInfo
            payload[1] = 6  # API_VERSION;
            payload[2] = 1  # FW_VERSION_MAJ;
            payload[3] = 0  # FW_VERSION_MIN;
            payload[4] = 0  # FW_VERSION_PATCH;
            payload[5:19] = b"rc3-3-g1d2f17d"
            sys.stderr.write(f"< {payload.hex()}\n")
            send(payload)

        elif msg[0] == Tokens.reqInit:
            send(bytes([Tokens.cnfInit, 0]))

        elif msg[0] == Tokens.reqTest:
            send(bytes([Tokens.cnfTest, 0]))
            send(bytes([Tokens.testRes]) + b"The following commands are available:\n")
            send(bytes([Tokens.testRes]) + b"setSingle [0..15] [1/0]\n")
            send(bytes([Tokens.testRes]) + b"setAll [0..FFFF]\n")
            send(bytes([Tokens.testRes]) + b"readEOLsensors\n")
            send(bytes([Tokens.testRes]) + b"readEncoders\n")
            send(bytes([Tokens.testRes]) + b"beep\n")
            send(bytes([Tokens.testRes]) + b"autoRead\n")
            send(bytes([Tokens.testRes]) + b"autoTest\n")
            send(bytes([Tokens.testRes]) + b"send\n")
            send(bytes([Tokens.testRes]) + b"stop\n")
            send(bytes([Tokens.testRes]) + b"quit\n")
            send(bytes([Tokens.testRes]) + b"help\n")

        msg = bytearray()
    else:
        msg.append(b)
