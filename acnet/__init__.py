"""This module provides access to the ACNET Control System via the
`acnetd` daemon (acnetd), allowing Python scripts to communicate with
ACNET services and resources.

This package targets Python3 and uses the async/await features of the
language to allow concurrent access.

To use this library, your main function should be marked `async` and
take a single parameter which will be the ACNET Connection object.
Your function should get passed to `acnet.run_client()`.

This library writes to the 'asyncio' logger. Your script can configure
the logger as it sees fit.


EXAMPLE #1: Specifying your script's starting function.

This simple example displays the ACNET handle that is assigned to the
script when it connects to ACNET. It shows how to register a starting
function and shows how it receives a Connection object you can use.

    import acnet

    async def main(con):
        print(f'assigned handle: {con.handle}')

    acnet.run_client(main)

Your function can create as many asynchronous tasks as it wants.
However, when the primary function returns, all other tasks will be
stopped and your script will continue execution after the
`acnet.run_client()` call.

The Connection object provides a low-level API to ACNET. Most Python
libraries will take this object and wrap an API around it when
supporting a popular ACNET service (e.g. DPM, LOOKUP, etc.)


EXAMPLE #2: Using Connection's low-level API to do node/name
            translations.

This example shows how to translate node names to and from node
addresses using the ACNET service with which the script is associated.

    import acnet

    async def my_client(con):
        # Look-up address of node CENTRA.

        name = 'CENTRA'
        addr = await con.get_addr(name)
        print(f'node {name} has address {addr}')

        # Do reverse look-up of CENTRA's address.

        name = await con.get_name(addr)
        print(f'node {addr} has name {name}')

    acnet.run_client(my_client)


EXAMPLE #3: Making a request for a single reply.

This snippet shows how a request is made to another ACNET task.

    import acnet

    async def my_client(con):

        # Send an ACNET "ping" message. This message is supported by
        # the ACNET task on every node.

        snd, sts, msg = await con.request_reply('ACNET@CENTRA', b'\x00\x00')
        snd = await con.get_name(snd)
        print(f'reply from {snd}: status={str(sts)}, msg={msg}')

    acnet.run_client(my_client)


EXAMPLE #4: Making simultaneous requests

This snippet looks up the addresses of three ACNET nodes simultaneously.

    import asyncio
    import acnet

    async def my_client(con):
        results = await asyncio.gather(
            con.get_addr('CENTRA'),
            con.get_addr('CENTRY'),
            con.get_addr('CLXSRV')
        )

        for ii in results:
            print(ii)

    acnet.run_client(my_client)
"""

import asyncio
import logging
import array
import socket
import struct
from collections import deque
import acnet.status

from acnet.status import ACNET_DISCONNECTED

_log = logging.getLogger('asyncio')

# This map and the two following functions define a framework which
# decodes incoming ACK packets.

_ackMap = {
    0: lambda buf: struct.unpack('>2xHh', buf),
    1: lambda buf: struct.unpack('>2xHhBI', buf),
    2: lambda buf: struct.unpack('>2xHhH', buf),
    4: lambda buf: struct.unpack('>2xHhBB', buf),
    5: lambda buf: struct.unpack('>2xHhI', buf),
    16: lambda buf: struct.unpack('>2xHhHI', buf)
}

def _throw_bug(_): raise status.ACNET_REQTMO

def _decode_ack(buf):
    return (_ackMap.get(buf[2] * 256 + buf[3], _throw_bug))(buf)

# This class defines the communication protocol between the client and
# acnetd.

class __AcnetdProtocol(asyncio.Protocol):
    def __init__(self):
        super().__init__()
        self.transport = None
        self.buffer = b''
        self.qCmd = asyncio.Queue(100)
        self._rpy_map = {}
        self._rpy_queue = []

    def __del__(self):
        self.end()

    def end(self):
        if self.transport:
            self.transport.close()
            self.transport = None

    def add_handler(self, reqid, handler):
        self._rpy_map[reqid] = handler

    def _get_packet(self):
        if len(self.buffer) >= 4:
            total = (self.buffer[0] << 24) + (self.buffer[1] << 16) + \
                    (self.buffer[2] << 8) + self.buffer[3]
            if len(self.buffer) >= total + 4:
                pkt = self.buffer[4:(total + 4)]
                self.buffer = self.buffer[(total + 4):]
                return pkt
        return None

    def pop_reqid(self, reqid):
        items = []
        rest = []
        for ii in self._rpy_queue:
            a, b, c, e, f = ii
            if a == reqid:
                items.append(ii)
            else:
                rest.append(ii)
        self._rpy_queue = rest
        return items

    def data_received(self, data):

        # Append to buffer and determine if enough data has arrived.

        self.buffer += data

        pkt = self._get_packet()

        while pkt is not None:
            pkt_type = pkt[0] * 256 + pkt[1]

            # Type 2 packets are ACKs for commands. There should
            # always be an element in the queue when we receive an
            # ACK.

            if pkt_type == 2:
                self.qCmd.get_nowait().set_result(bytearray(pkt))

            # Type 3 packets are ACNET reply traffic.

            elif pkt_type == 3:

                # Split out the interesting fields of the ACNET header.

                (flg, sts, t, n, reqid) = struct.unpack_from('<HhBB8xH', pkt,
                                                             offset=2)
                replier = t * 256 + n
                last = (flg & 1) == 0

                # Check to see if there's a function associated with
                # the request ID

                f = self._rpy_map.get(reqid)
                if f:
                    # If bit 0 is clear, this is the last reply so
                    # we remove the entry from the map.

                    if last:
                        del self._rpy_map[reqid]

                    sts = status.Status(sts)

                    # Send the 3-tuple, (sender, status, message)
                    # to the recipient.

                    if sts != status.ACNET_PEND:
                        f((replier, sts, pkt[20:]), last)
                else:
                    self._rpy_queue.append((reqid, replier, sts, pkt[20:], last))
            pkt = self._get_packet()

    # Gets called when the transport successfully connects. We send
    # out the RAW header to tell acnetd we're using the TCP socket in
    # RAW mode (instead of WebSocket mode.)

    def connection_made(self, transport):
        self.transport = transport
        self.transport.write(b'RAW\r\n\r\n')
        _log.debug('connected to ACNET')

    def connection_lost(self, exc):
        self.end()
        _log.warning('lost connection with ACNET')

        # Loop through all active requests and send a message
        # indicating the request is done.

        msg = (0, ACNET_DISCONNECTED, b'')
        for _, f in self._rpy_map.items():
            f(msg, True)
        self._rpy_map = {}

	# Send an error to all pending ACKs. The '\xde\x01' value is
	# ACNET_DISCONNECTED.

        msg = b'\x00\x00\xde\x01'
        while not self.qCmd.empty():
            self.qCmd.get_nowait().set_result(msg)

    def error_received(self, exc):
        _log.error('ACNET socket error', exc_info=True)

    async def xact(self, buf):
        ack_fut = asyncio.get_event_loop().create_future()
        await self.qCmd.put(ack_fut)
        if self.transport is not None:
            self.transport.write(buf)
            return _decode_ack(await ack_fut)
        else:
            raise ACNET_DISCONNECTED

# This class manages the connection between the client and acnetd. It
# defines the public API.

class Connection:
    """Manages and maintains a connection to the ACSys control system. In
addition to methods that make requests, this object has methods that
directly interact with the local ACNET service."""

    def __init__(self):
        """Constructor.

Creates a disconnected instance of a Connection object. This instance
can't be properly used until further steps are completed.  SCRIPTS
SHOULDN'T CREATE CONNECTIONS; they should receive a properly created
one indirectly through `acnet.run_client()`.
        """
        self._raw_handle = 0
        self.handle = None
        self.protocol = None

    def __del__(self):
        if self.protocol is not None:
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

        return str.strip(result.tostring().decode('ascii'))

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

    async def _xact(self, buf):
        if self.protocol is not None:
            while True:
                try:
                    return await self.protocol.xact(buf)
                except acnet.status.Status as sts:
                    if sts != ACNET_DISCONNECTED or self.protocol is None:
                        raise

                # We got an ACNET_DISCONNECTED. Try to reconnect.

                self.protocol = None
                while self.protocol is None:
                    await asyncio.sleep(2)
                    _log.info('retrying connection to ACNET')
                    proto = await _create_socket()
                    try:
                        await self._connect(proto)
                    except:
                        pass
        else:
            raise ACNET_DISCONNECTED

    # Used to tell acnetd to cancel a specific request ID. This method
    # doesn't return an error; if the request ID existed, it'll be
    # gone and if it didn't, it's still gone.

    async def _cancel(self, reqid):
        buf = struct.pack('>I2H2IH', 14, 1, 8, self._raw_handle, 0, reqid)
        await self._xact(buf)

    # acnetd needs to know when a client is ready to receive replies
    # to a request. This method informs acnetd which request has been
    # prepared.

    async def _ack_request(self, reqid):
        buf = struct.pack('>I2H2IH', 14, 1, 9, self._raw_handle, 0, reqid)
        await self._xact(buf)

    # Finish initializing a Connection object. The construction can't
    # block for the CONNECT command so we have to initialize in two
    # steps.

    async def _connect(self, proto):

        # Send a CONNECT command requesting an anonymous handle and
        # get the reply. Use 'proto' directly to call '.xact()' since
        # 'self.protocol' hasn't been assigned yet. This prevents
        # other clients from using the Connection until we register
        # and get a handle.

        _log.debug('registering with ACNET')
        buf = struct.pack('>I2H3IH', 18, 1, 1, self._raw_handle, 0, 0, 0)
        res = await proto.xact(buf)
        sts = status.Status(res[1])

        # A good reply is a tuple with 4 elements.

        if sts.isSuccess and len(res) == 4:
            self.protocol = proto
            self._raw_handle = res[3]
            self.handle = Connection.__rtoa(res[3])
            _log.info('connected to ACNET with handle %s', self.handle)
        else:
            raise sts

    async def get_name(self, addr):
        """Look-up node name.

Returns the ACNET node name associated with the ACNET node address,
`addr`.
        """
        if isinstance(addr, int) and addr >= 0 and addr <= 0x10000:
            buf = struct.pack('>I2H2IH', 14, 1, 12, self._raw_handle, 0, addr)
            res = await self._xact(buf)
            sts = status.Status(res[1])

            # A good reply is a tuple with 4 elements.

            if sts.isSuccess and len(res) == 3:
                return Connection.__rtoa(res[2])
            else:
                raise sts
        else:
            raise ValueError('addr must be in the range of a 16-bit, signed integer')

    async def get_addr(self, name):
        """Look-up node address.

Returns the ACNET trunk/node node address associated with the ACNET
node name, `name`.
        """
        if isinstance(name, str) and len(name) <= 6:
            buf = struct.pack('>I2H3I', 16, 1, 11, self._raw_handle, 0,
                              Connection.__ator(name))
            res = await self._xact(buf)
            sts = status.Status(res[1])

            # A good reply is a tuple with 4 elements.

            if sts.isSuccess and len(res) == 4:
                return res[2] * 256 + res[3]
            else:
                raise sts
        else:
            raise ValueError('name must be a string of no more than 6 characters')

    async def _to_trunknode(self, node):
        if isinstance(node, str):
            return await self.get_addr(node)
        elif not isinstance(node, int):
            raise ValueError('node should be an integer or string')
        else:
            return node

    async def _to_nodename(self, node):
        if isinstance(node, int):
            return await self.get_name(node)
        elif not isinstance(node, str):
            raise ValueError('node should be an integer or string')
        else:
            return node

    async def _split_taskname(self, taskname):
        part = taskname.split('@', 1)
        if len(part) == 2:
            addr = await self.get_addr(part[1])
            return (Connection.__ator(part[0]), addr)
        else:
            raise ValueError('too many @ characters')

    async def _mk_req(self, remtsk, message, mult, proto, timeout):
        if proto:
            if hasattr(message, 'marshal'):
                message = bytearray(message.marshal())
            else:
                raise ValueError('message wasn''t created by the protocol compiler')

        if isinstance(message, (bytes, bytearray)) and isinstance(timeout, int):
            task, node = await self._split_taskname(remtsk)
            buf = struct.pack('>I2H3I2HI', 24 + len(message), 1, 18,
                              self._raw_handle, 0, task, node, mult,
                              timeout) + message
            res = await self._xact(buf)
            sts = status.Status(res[1])

            # A good reply is a tuple with 4 elements.

            if sts.isSuccess and len(res) == 3:
                return res[2]
            else:
                raise sts
        else:
            raise ValueError('message must be a binary')

    async def request_reply(self, remtsk, message, *, proto=None, timeout=1000):
        """Request a single reply from an ACNET task.

This function sends a request to an ACNET task and returns a future
which will be resolved with the reply. The reply is a 3-tuple where
the first element is the trunk/node address of the sender, the second
is the ACNET status of the request, and the third is the reply
data.

The ACNET status will always be good (i.e. success or warning);
receiving a fatal status results in the future throwing an exception.

'remtsk' is a string representing the remote ACNET task in the format
"TASKNAME@NODENAME".

'message' is either a bytes type, or a type that's an acceptable value
for a protocol (specified by the 'proto' parameter.)

'proto' is an optional, named parameter. If omitted, the message must
be a bytes type. If specified, it should be the name of a module
generated by the Protocol Compiler.

'timeout' is an optional field which sets the timeout for the
request. If the reply doesn't arrive in time, an ACNET_UTIME status
will be raised.

If the message is in an incorrect format or the timeout parameter
isn't an integer, ValueError is raised.
        """
        reqid = await self._mk_req(remtsk, message, 0, proto, timeout)

        # Create a future which will eventually resolve to the
        # reply.

        loop = asyncio.get_event_loop()
        rpy_fut = loop.create_future()

        # Define a function we can use to stuff the future
        # with the reply. If the status is fatal, this
        # function will resolve the future with an exception.
        # Otherwise the reply message is set as the result.

        def reply_handler(reply, _):
            snd, sts, data = reply
            if not sts.isFatal:
                if proto:
                    reply = (snd, sts, proto.unmarshal_reply(iter(data)))
                rpy_fut.set_result(reply)
            else:
                rpy_fut.set_exception(sts)

        # Save the handler in the map and return the future. BTW, we
        # don't have to test for the validity of 'self.protocol' here
        # because, to reach this point, the previous call to
        # `._mk_req` didn't throw an exception (which it would have if
        # `self.protocol` was None.

        replies = self.protocol.pop_reqid(reqid)
        if len(replies) == 0:
            self.protocol.add_handler(reqid, reply_handler)
            return (await rpy_fut)
        else:
            return (replies[0][1], replies[0][2], replies[0][3])

    async def request_stream(self, remtsk, message, *, proto=None, timeout=1000):
        """Request a stream of replies from an ACNET task.

This function sends a request to an ACNET task and returns an async
generator which returns the stream of replies. Each reply is a 3-tuple
where the first element is the trunk/node address of the sender, the
second is the ACNET status of the request, and the third is the reply
data.

The ACNET status in each reply will always be good (i.e. success or
warning); receiving a fatal status results in the generator throwing
an exception.

'remtsk' is a string representing the remote ACNET task in the format
"TASKNAME@NODENAME".

'message' is either a bytes type, or a type that's an acceptable value
for a protocol (specified by the 'proto' parameter.)

'proto' is an optional, named parameter. If omitted, the message must
be a bytes type. If specified, it should be the name of a module
generated by the Protocol Compiler.

'timeout' is an optional field which sets the timeout between each
reply.  If any reply doesn't arrive in time, an ACNET_UTIME status
will be raised.

If the message is in an incorrect format or the timeout parameter
isn't an integer, ValueError is raised.
        """
        try:
            reqid = await self._mk_req(remtsk, message, 1, proto, timeout)
            rpy_q = asyncio.Queue()
            done = False

            def handler(rpy, last):
                rpy_q.put_nowait(rpy)
                done = last

            # Pre-stuff the queue with replies that may already have
            # arrived. BTW, we don't have to test for the validity of
            # 'self.protocol' here because, to reach this point, the
            # previous call to `._mk_req` didn't throw an exception
            # (which it would have if `self.protocol` was None.

            for _, snd, sts, pkt, last in self.protocol.pop_reqid(reqid):
                handler((snd, sts, pkt), last)

            # Save the handler in the map.

            self.protocol.add_handler(reqid, handler)
            await self._ack_request(reqid)

            # This section implements the async generator.

            while not done:
                snd, sts, msg = await rpy_q.get()
                if not sts.isFatal:
                    if proto is not None and len(msg) > 0:
                        msg = proto.unmarshal_reply(iter(msg))
                    yield (snd, sts, msg)
                else:
                    raise sts
        finally:
            _log.debug('canceling request %d', reqid)
            await self._cancel(reqid)

    async def ping(self, node):
        """Pings an ACNET node.

        Uses the Level2 protocol to perform an ACNET ping
        request. Returns True if the node responded or False if it
        didn't. A node is given 1/4 second to respond. If the
        Connection has problems, this method will raise an ACNET
        Status code.
        """
        node = await self._to_nodename(node)
        try:
            await self.request_reply('ACNET@' + node, b'\x00\x00')
            return True
        except acnet.status.Status as e:
            if e == acnet.status.ACNET_REQTMO:
                return False
            else:
                raise e

async def _create_socket():
    try:
        s = socket.create_connection(('firus-gate.fnal.gov', 6802), 0.25)
    except socket.timeout:
        _log.warning('timeout connecting to ACNET')
        return None
    else:
        loop = asyncio.get_event_loop()
        _log.info('creating ACNET transport')
        _, proto = await loop.create_connection(lambda: __AcnetdProtocol(),
                                                sock=s)
        return proto

async def __client_main(main):
    proto = await _create_socket()
    if proto is not None:
        con = Connection()
        try:
            await con._connect(proto)
            await main(con)
        finally:
            del con
    else:
        _log.error('*** unable to connect to ACNET')
        raise ACNET_DISCONNECTED

def run_client(main):
    """Starts an asynchronous session for ACNET clients. `main` is an
async function which will receive a fully initialized Connection
object. When 'main' resolves, this function will return.
    """
    asyncio.get_event_loop().run_until_complete(__client_main(main))
