import asyncio
import array
import struct
from collections import deque
import status

# This map and the two following functions define a framework which
# decodes incoming ACK packets.

__ackMap = {
    0: lambda buf: struct.unpack(">2xHh", buf),
    1: lambda buf: struct.unpack(">2xHhBI", buf),
    2: lambda buf: struct.unpack(">2xHhH", buf),
    4: lambda buf: struct.unpack(">2xHhBB", buf),
    5: lambda buf: struct.unpack(">2xHhI", buf),
    16: lambda buf: struct.unpack(">2xHhHI", buf)
}

def __throw_bug(buf): raise Status.ACNET_REQTMO

def decode_ack(buf):
    return (__ackMap.get(buf[2] * 256 + buf[3], __throw_bug))(buf)

# This class defines the communication protocol between the client and
# acnetd.

class __AcnetdProtocol(asyncio.Protocol):
    def __init__(self):
        self.transport = None
        self.buffer = []
        self.qCmd = deque()

    def __del__(self):
        if self.transport:
            self.transport.close();

    def end(self):
        if self.transport:
            self.transport.close()
            self.transport = None

    def data_received(self, data):

        # Append to buffer and determine if enough data has arrived.

        self.buffer += data
        total = (data[0] << 24) + (data[1] << 16) + (data[2] << 8) + data[3]
        if len(self.buffer) >= total + 4:

            # Strip off the leading packet. Leave the remaining data
            # in `self.buffer`.

            pkt = self.buffer[4:(total + 4)]
            self.buffer = self.buffer[(total + 4):]
            pkt_type = data[4] * 256 + data[5]

            # Type 2 packets are synchronous ACKs for commands.

            if pkt_type == 2:
                self.qCmd.popleft().set_result(bytearray(pkt))

    def connection_made(self, transport):
        self.transport = transport
        self.transport.write(b'RAW\r\n\r\n')

    def connection_lost(self, exc):
        if exc != None:
            print("unexpected loss of connection:", exc)
            self.end()

    def error_received(self, exc):
        print('Error received:', exc)

    async def xact(self, buf):
        ack_fut = asyncio.get_event_loop().create_future()
        self.qCmd.append(ack_fut)
        self.transport.write(buf)
        ack_buf = await ack_fut
        return decode_ack(ack_buf)

# This class manages the connection between the client and acnetd. It
# defines the public API.

class Connection:
    """Manages and maintains a connection to the ACSys control system.
    """

    def __init__(self, proto):
        self.handle = None
        self.protocol = proto

    def __del__(self):
        self.protocol.end()
    # Convert rad50 value to a string
    @staticmethod
    def __rtoa(r50):
        result = array.array('B', b'      ')
        chars = array.array('B', b' ABCDEFGHIJKLMNOPQRSTUVWXYZ$.%0123456789')

        first_bit = r50 & 0xffff
        second_bit = (r50 >> 16) & 0xffff

        for index in range(0, 3):
            result[int(2 - index)] = chars[int(first_bit % 40)]
            first_bit /= 40
            result[int(5 - index)] = chars[int(second_bit % 40)]
            second_bit /= 40

        return result.tostring()

    # Convert a string to rad50 value
    @staticmethod
    def __ator(input_string):
        def char_to_index(char):
            if 'A' <= char <= 'Z':
                return ord(char) - ord('A') + 1
            if 'a' <= char <= 'z':
                return ord(char) - ord('a') + 1
            if '0' <= char <= '9':
                return ord(char) - ord('0') + 30
            if char == '$':
                return 27
            if char == '.':
                return 28
            if char == '%':
                return 29
            return 0

        first_bit = 0
        second_bit = 0
        s_len = len(input_string)
        for index in range(0, 6):
            char = input_string[index] if index < s_len else ' '

            if index < (6 / 2):
                first_bit *= 40
                first_bit += char_to_index(char)
            else:
                second_bit *= 40
                second_bit += char_to_index(char)

        return (second_bit << 16) | first_bit

    async def connect(self):
        # Send a CONNECT command requesting an anonymous handle and
        # get the reply.

        buf = struct.pack(">I2h3ih", 18, 1, 1, 0, 0, 0, 0)
        res = await self.protocol.xact(buf)
        if len(res) == 4:
            self.handle = Connection.__rtoa(res[3])
        else:
            raise status.Status(res[1])

    async def requestSingle(task, message):
        pass

    async def requestMultiple(task, message):
        pass

async def __client_main(loop, main):
    try:
        _, proto = await loop.create_connection(lambda: __AcnetdProtocol(),
                                                'firus-gate.fnal.gov', 6802)
    except TimeoutError:
        print('timeout occurred while trying to connect to ACNET')
    else:
        con = Connection(proto)

        try:
            await con.connect()
            await main(con)
        finally:
            del con

def run_client(main):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(__client_main(loop, main))

async def my_client(con):
    print('handle: ', con.handle)
    await asyncio.sleep(3600)

if __name__ == '__main__':
    run_client(my_client)
