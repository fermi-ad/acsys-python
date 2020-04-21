import asyncio
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

    async def connect(self):
        # Send a CONNECT command requesting an anonymous handle and
        # get the reply.

        buf = struct.pack(">I2h3ih", 18, 1, 1, 0, 0, 0, 0)
        res = await self.protocol.xact(buf)
        if len(res) == 4:
            self.handle = res[3]
        else:
            raise status.Status(res[1])

    async def requestSingle(task, message):
        pass

    async def requestMultiple(task, message):
        pass

async def __client_main(loop, main):
    try:
        _, proto = await loop.create_connection(lambda: __AcnetdProtocol(),
                                                'acsys-proxy.fnal.gov', 6802)
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
