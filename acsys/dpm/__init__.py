import asyncio
import importlib
import logging
import getpass
import os
import sys
from datetime import (timezone, datetime, timedelta)
import acsys.status
from acsys.dpm.dpm_protocol import (ServiceDiscovery_request,
                                    AddToList_request,
                                    RemoveFromList_request,
                                    StartList_request,
                                    StopList_request,
                                    ClearList_request,
                                    RawSetting_struct,
                                    TextSetting_struct,
                                    ScaledSetting_struct,
                                    ApplySettings_request,
                                    Status_reply, AnalogAlarm_reply,
                                    BasicStatus_reply,
                                    DigitalAlarm_reply,
                                    DeviceInfo_reply, Raw_reply,
                                    ScalarArray_reply, Scalar_reply,
                                    TextArray_reply, Text_reply,
                                    ListStatus_reply,
                                    ApplySettings_reply,
                                    Authenticate_request,
                                    EnableSettings_request,
                                    TimedScalarArray_reply,
                                    Authenticate_reply,
                                    unmarshal_reply)

_log = logging.getLogger(__name__)


class ItemData:
    """An object that holds a reading from a device.

DPM delivers device data using a stream of ItemData objects. The 'tag'
field corresponds to the tag parameter used when the '.add_entry()'
method was used to add the device to the list.

    """

    def __init__(self, tag, stamp, data, micros=None, meta=None):
        self._tag = tag
        self._meta = (meta or {})
        base_time = datetime(1970, 1, 1, tzinfo=timezone.utc)
        if micros is None:
            self._data = [(base_time + timedelta(milliseconds=stamp), data)]
        else:
            self._data = list(zip([base_time + timedelta(microseconds=stamp) for stamp in micros], data))

    @property
    def tag(self):
        """Corresponds to the ref ID that was associated with the DRF request
string."""
        return self._tag

    @property
    def data(self):
        """An array of timestamp/value pairs. The value will be of the type
asked in the corresponding DRF2 (specified in the call to the
'.add_entry()' method.) For instance, if .RAW was specified, the value
field will contain a bytes(). Otherwise it will contain a scaled,
floating point value (or an array, if it's an array device), or a
dictionary -- in the case of basic status or alarm blocks.

        """
        return self._data

    @property
    def stamp(self):
        return self._data[0][0]

    @property
    def value(self):
        return self._data[0][1]

    @property
    def meta(self):
        """Contains a dictionary of extra information about the device. The
'name' key holds the device name. 'di' contains the device index. If
the device has scaling, a 'units' key will be present and hold the
engineering units of the reading.

        """
        return self._meta

    def __str__(self):
        return f'{{ tag: {self.tag}, data: {self.data}, meta: {self.meta} }}'

    def is_reading_for(self, *tags):
        """Returns True if this ItemData instance is associated with any of
the tag values in the parameter list.

        """
        return self.tag in tags

    def is_status_for(self, *_tags):
        """Returns False."""
        return False


class ItemStatus:
    """An object reporting status of an item in a DPM list.

If there was an error in a request, this object will be in the stream
instead of a ItemData object. The 'tag' field corresponds to the tag
parameter used in the call to the '.add_entry()' method.

If this message appears as a result of a reading request, there will
never be an ItemData object for the 'tag' until the error condition is
fixed and the list restarted.

There will always be one of these objects generated to indicate the
result of a setting.

    """

    def __init__(self, tag, status):
        self._tag = tag
        self._status = acsys.status.Status(status)

    @property
    def tag(self):
        """Corresponds to the ref ID that was associated with the DRF request
string."""
        return self._tag

    @property
    def status(self):
        """Describes the error that occurred with this item."""
        return self._status

    def __str__(self):
        return f'{{ tag: {self.tag}, status: {self.status} }}'

    def is_reading_for(self, *_tags):
        """Returns False."""
        return False

    def is_status_for(self, *tags):
        """Returns True if this ItemStatus instance is associated with any of
the tag values in the parameter list.

        """
        return self.tag in tags


class DPM(asyncio.Protocol):
    """An object that manages a connection to a remote Data Pool Manager
(DPM). Instances of this class should be obtained by a 'DPMContext'
object used in an 'async-with' statement.

Creating an instance results in a dormant object. To activate it, it
needs to be passed as the 'protocol' argument to 'asyncio.create_connection()'.

'DPMContext's in an `async-statement' perform this initialization for
you as well as clean-up properly.

    """

    # Constructor -- this simply defines the object instance and puts
    # it in a dormant state. Passing it to 'asyncio.create_connection()'
    # will activate it.

    def __init__(self, port):
        super().__init__()

        # These properties can be accessed without owning '_state_sem'
        # because they're either constant or concurrent-safe or
        # they're not manipulated across 'await' statements.

        self.meta = {}
        self.port = port
        self.buf = bytearray()
        self._qdata = asyncio.Queue()   # queue to hold incoming
                                        # acquisition replies

        self._state_sem = asyncio.Semaphore()

        # When accessing these properties, '_state_sem' must be owned.

        self._transport = asyncio.get_event_loop().create_future()
        self._dev_list = {}             # set of staged DRF requests
        self._active_dev_list = {}      # DRFs being used in active
                                        # acquisition
        self._qrpy = []                 # queue holding futures to be
                                        # resolved when a reply is
                                        # received
        self.active = False             # flag indicating acquisition status
        self.can_set = False            # flag indicating settings are enabled
        self.model = None               # default model to be used by
                                        # connection
        self.req_tmo = 2000             # ms timeout for replies

    # The '._transport' field of a DPM instance is always a
    # 'Future'. The constructor sets it to an unresolved future. The
    # '.connection_made()' callback will resolve it with the actual transport.

    async def _get_transport(self):
        try:
            return await asyncio.wait_for(self._transport, timeout=None)
        except asyncio.TimeoutError as exc:
            raise acsys.status.ACNET_DISCONNECTED from exc

    # We use the state of the DPM object to initialize the state of
    # the connection. This means a new DPM object will do the minimum
    # to prepare the connection's state whereas a connection returning
    # data will get its DRF requests setup and started.

    async def _setup_state(self, transport):
        async with self._state_sem as lock:
            _log.debug('setting up DPM state')
            self._transport.set_result(transport)

            # The pending replies from a previous connection should
            # have been cleared out before we start a new one.

            assert self._qrpy == []

            await self._add_to_list(lock, 0, f'#USER:{getpass.getuser()}')
            await self._add_to_list(lock, 0, f'#PID:{os.getpid()}')
            await self._add_to_list(lock, 0, '#TYPE:Python3/TCP')

            # Did we have settings enabled in a previous connection?
            # If so, enable them again.

            if self.can_set:
                _log.debug('re-enabling settings')
                await self.enable_settings()

            # Load up all the DRF requests.

            for tag, drf in self._active_dev_list.items():
                await self._add_to_list(lock, tag, drf)

            # If the previous connection was running acquisition,
            # start it up again.

            if self.active:
                _log.debug('re-activating data acquisition')
                await self.start(self.model)

    # Called when the connection is lost or when closing out a DPM
    # connection. It closes the connection to DPM, if it was open, and
    # then makes sure all queue are drained so connecting to another
    # DPM will start with initialized state. All DRF lists are
    # preserved so that the DPM state can be restored.

    async def _shutdown_state(self, restart=False):
        _log.debug('shutting down DPM state')
        async with self._state_sem:

            # Clean up the transport resources.

            (await self._get_transport()).abort()
            self._transport = asyncio.get_event_loop().create_future()

            # Loop through all pending requests and resolve them with
            # exceptions.

            for ii in self._qrpy:
                ii.set_exception(acsys.status.ACNET_DISCONNECTED)
            self._qrpy = []

        # Must do this outside the previous block because tasks
        # reading the queue contents may have to grab the semaphore
        # and we don't want to dead-lock.

        _log.debug('waiting for reply queue to be drained')
        await asyncio.wait_for(self._qdata.join(), 1000)

        if restart:
            self.connect()

    # Called when the TCP socket has connected to the remote machine.
    # The 'transport' parameter is the object to use to write data to
    # the remote end. A future is scheduled to initialize the state of
    # the DPM object.

    def connection_made(self, transport):
        self.buf = bytearray()
        _log.info('connected to DPM')
        transport.write(b'GET /dpm HTTP/1.1\r\n\r\n')
        asyncio.ensure_future(self._setup_state(transport))

    # Called when we lose our connection to DPM.

    def connection_lost(self, exc):
        if exc is not None:
            _log.warning('lost connection to DPM, %s', exc)
            asyncio.ensure_future(self._shutdown_state(restart=True))
        else:
            _log.debug('closed connection to DPM')

    @staticmethod
    def _get_packet(buf):
        if len(buf) >= 4:
            total = (buf[0] << 24) + (buf[1] << 16) + \
                (buf[2] << 8) + buf[3]
            if len(buf) >= total + 4:
                return (iter(memoryview(buf)[4:(total + 4)]),
                        buf[(total + 4):])
        return (None, buf)

    def data_received(self, data):
        self.buf += data
        pkt, rest = DPM._get_packet(self.buf)
        while pkt is not None:
            msg = self._xlat_reply(unmarshal_reply(pkt))

            if isinstance(msg, list):
                for ii in msg:
                    self._qdata.put_nowait(ii)
            elif isinstance(msg, (ItemData, ItemStatus)):
                self._qdata.put_nowait(msg)
            elif msg is not None:
                self._qrpy[0].set_result(msg)
                self._qrpy.pop()

            pkt, rest = DPM._get_packet(rest)
        self.buf = rest

    def _xlat_reply(self, msg):
        if isinstance(msg, Status_reply):
            return ItemStatus(msg.ref_id, msg.status)
        if isinstance(msg, (AnalogAlarm_reply,
                            DigitalAlarm_reply,
                            BasicStatus_reply)):
            return ItemData(msg.ref_id, msg.timestamp, msg.__dict__,
                            meta=self.meta.get(msg.ref_id, {}))
        if isinstance(msg, (Raw_reply,
                            ScalarArray_reply,
                            Scalar_reply,
                            TextArray_reply,
                            Text_reply)):
            return ItemData(msg.ref_id, msg.timestamp, msg.data,
                            meta=self.meta.get(msg.ref_id, {}))
        if isinstance(msg, ApplySettings_reply):
            return [ItemStatus(reply.ref_id, reply.status)
                    for reply in msg.status]
        if isinstance(msg, ListStatus_reply):
            return None
        if isinstance(msg, DeviceInfo_reply):
            self.meta[msg.ref_id] = \
                {'di': msg.di, 'name': msg.name,
                 'desc': msg.description,
                 'units': msg.units if hasattr(msg, 'units') else None,
                 'format_hint': msg.format_hint if hasattr(msg, 'format_hint')
                 else None}
            return None
        if isinstance(msg, TimedScalarArray_reply):
            return ItemData(msg.ref_id, msg.timestamp, msg.data,
                            meta=self.meta.get(msg.ref_id, {}),
                            micros=msg.micros)
        return msg

    async def connect(self):
        loop = asyncio.get_event_loop()
        con_fut = loop.create_connection(lambda: self,
                                         host='acsys-proxy.fnal.gov',
                                         port=self.port)
        await asyncio.wait_for(con_fut, 2000)

        # To reach this spot, two things will have happened: 1) we
        # actually made a connection to a remote DPM. If we didn't, an
        # exception would be raised. And 2) the .connect_made() method
        # has been called and finished executing. At this point,
        # ._setup_state() has been scheduled, but might not have
        # completed yet. We can't return yet because the user's script
        # may try to send requests to DPM. So we block here until the
        # future that holds the transport gets resolved.

        await self._transport

    async def replies(self, tmo=None, model=None):
        """Returns an async generator which yields each reply from DPM. The
optional `tmo` parameter indicates how long to wait between replies
before an `asyncio.TimeoutError` is raised.

        """
        should_stop = False

        try:
            # If we're not active, then the user is expexting this
            # generator to do the start/stop management.

            if not self.active:
                await self.start(model)
                should_stop = True

            while True:
                pkt = await asyncio.wait_for(self._qdata.get(), tmo)
                self._qdata.task_done()
                yield pkt
        finally:
            # The generator has been exited. If this function started
            # acquisition, then it should stop it. When we get a reply
            # for the `.stop()`, we know we won't get any more data
            # replies. `._qdata` may contain some stale entries so we
            # throw it away and create a new, empty queue.

            if should_stop:
                await self.stop()
                self._qdata = asyncio.Queue()

    async def get_entry(self, tag, active=False):
        """Returns the DRF string associated with the 'tag'.

The DPM object keeps track of two sets of DRF requests; one set
represents requests which become active after a call to 'DPM.start()'.
The other set is defined when data acquisition is active.

If the 'active' parameter is False or data acquisition isn't
happening, the staged requests are searched. If 'active' is True and
acquisition is happening, the active requests are searched.

        """
        async with self._state_sem:
            if active and self.active:
                return self._active_dev_list.get(tag)
            return self._dev_list.get(tag)

    # Makes a request to DPM.

    async def _mk_request(self, _lock, msg, wait=False):
        xport = await self._get_transport()
        msg = bytes(msg.marshal())
        xport.write(len(msg).to_bytes(4, byteorder='big') + msg)
        if wait:
            fut = asyncio.get_event_loop().create_future()
            self._qrpy.append(fut)
            return fut
        return None

    async def clear_list(self):
        """Clears all entries in the tag/drf dictionary.

Clearing the list doesn't stop incoming data acquisition, it clears
the list to be sent with the next call to 'dpm.start()'. To stop data
acquisition, call 'dpm.stop()'.

        """
        msg = ClearList_request()
        msg.list_id = 0                 # ignored in TCP connections
        _log.debug('clearing list')

        async with self._state_sem as lock:
            await self._mk_request(lock, msg)
            self._dev_list = {}

    async def _add_to_list(self, lock, tag, drf):
        msg = AddToList_request()

        msg.list_id = 0                 # ignored in TCP connections
        msg.ref_id = tag
        msg.drf_request = drf

        # Perform the request. If the request returns a fatal error,
        # the status will be raised for us. If the DPM returns a fatal
        # status in the reply message, we raise it ourselves.

        _log.debug('adding tag:%d, drf:%s', tag, drf)
        await self._mk_request(lock, msg)

        # DPM has been updated so we can safely add the entry to our
        # device list. (We don't add entries starting with "#" because
        # those are property hacks.

        if drf[0] != "#":
            self._dev_list[tag] = drf

    async def add_entry(self, tag, drf):
        """Add an entry to the list of devices to be acquired.

This updates the list of device requests. The 'tag' parameter is used
to mark this request's device data. When the script starts receiving
ItemData objects, it can correlate the data using the 'tag' field. The
'tag' must be an integer -- the method will raise a ValueError if it's
not.

The 'drf' parameter is a DRF2 string representing the data to be read
along with the sampling event. If it isn't a string, ValueError will
be raised.

If this method is called with a tag that was previously used, it
replaces the previous request. If data is currently being returned, it
won't reflect the new entry until the 'start' method is called.

If simultaneous calls are made to this method and all are using the
same 'tag', which 'drf' string is ultimately associated with the tag
is non-deterministic.

        """

        # Make sure the tag parameter is an integer and the drf
        # parameter is a string. Otherwise throw a ValueError
        # exception.

        if isinstance(tag, int):
            if isinstance(drf, str):
                async with self._state_sem as lock:
                    await self._add_to_list(lock, tag, drf)
            else:
                raise ValueError('drf must be a string')
        else:
            raise ValueError('tag must be an integer')

    async def add_entries(self, entries):
        """Adds multiple entries.

This is a convenience function to add a list of tag/drf pairs to DPM's
request list.
        """

        # Validate the array of parameters.

        for tag, drf in entries:
            if not isinstance(tag, int):
                raise ValueError(f'tag must be an integer -- found {tag}')
            if not isinstance(drf, str):
                raise ValueError('drf must be a string -- found {drf}')

        async with self._state_sem as lock:
            for tag, drf in entries:
                await self._add_to_list(lock, tag, drf)

    async def remove_entry(self, tag):
        """Removes an entry from the list of devices to be acquired.

This updates the list of device requests. The 'tag' parameter is used
to specify which request should be removed from the list.  The 'tag'
must be an integer -- the method will raise a ValueError if it's not.

Data associated with the 'tag' will continue to be returned until the
'.start()' method is called.

        """

        # Make sure the tag parameter is an integer and the drf
        # parameter is a string. Otherwise throw a ValueError
        # exception.

        if isinstance(tag, int):
            # Create the message and set the fields appropriately.

            msg = RemoveFromList_request()
            msg.list_id = 0             # ignored in TCP connections
            msg.ref_id = tag
            _log.debug('removing tag:%d', tag)

            async with self._state_sem as lock:
                await self._mk_request(lock, msg)

                # DPM has been updated so we can safely remove the
                # entry from our device list.

                del self._dev_list[tag]
        else:
            raise ValueError('tag must be an integer')

    async def start(self, model=None):
        """Start/restart data acquisition using the current request list.

Calls to '.add_entry()' and '.remove_entry()' make changes to the list
of requests but don't actually affect data acquisition until this
method is called. This allows a script to make major adjustments and
then enable the changes all at once.

        """
        _log.debug('starting DPM list')
        self.model = model
        msg = StartList_request()
        msg.list_id = 0                 # ignored in TCP connections

        if self.model:
            msg.model = self.model

        async with self._state_sem as lock:
            fut = await self._mk_request(lock, msg, wait=True)
            self.active = True
            self._active_dev_list = self._dev_list.copy()
            await fut

    async def stop(self):
        """Stops data acquisition.

This method stops data acquisition. The list of requests is unaffected
so a call to '.start()' will restart the list.

Due to the asynchronous nature of network communications, after
calling this method, a few readings may still get delivered.

        """

        msg = StopList_request()
        msg.list_id = 0
        _log.debug('stopping DPM list')

        async with self._state_sem as lock:
            await self._mk_request(lock, msg)
            self.active = False
            self._active_dev_list = {}

    @staticmethod
    def _build_struct(ref_id, value):
        if isinstance(value, (bytearray, bytes)):
            set_struct = RawSetting_struct()
        elif isinstance(value, str):
            if not isinstance(value, list):
                value = [value]
            set_struct = TextSetting_struct()
        else:
            if not isinstance(value, list):
                value = [value]
            set_struct = ScaledSetting_struct()

        set_struct.ref_id = ref_id
        set_struct.data = value
        return set_struct

    # Performs one round-trip of the Kerberos validation.

    async def _auth_step(self, lock, tok):
        msg = Authenticate_request()
        msg.list_id = 0
        if tok is not None:
            msg.token = tok

        fut = await self._mk_request(lock, msg, wait=True)

        msg = await fut
        if not isinstance(msg, Authenticate_reply):
            raise TypeError(f'unexpected protocol message: %{msg}')
        return msg

    async def enable_settings(self, role=None):
        """Enable settings for the current DPM session.

This method exchanges credentials with the DPM. If successful, the
session is allowed to make settings. The script must be running in an
environment with a valid Kerberos ticket. The ticket must part of the
FNAL.GOV realm and can't be expired.

The credentials are valid as long as this session is maintained.

The `role` parameter indicates in what role your script will be
running. Your Kerberos principal should be authorized to operate in
the role.

        """

        # Lazy load the gssapi library so that this doesn't block users
        # who are only doing readings.

        spec = importlib.util.find_spec('gssapi')
        if spec is None:
            _log.error('Cannot find the gssapi module')
            print('To enable settings, the "gssapi" module must be installed.')
            print(('Run `pip install "acsys[settings]"` '
                   'to install the required library.'))
            sys.exit(1)

        # Perform the actual import

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        gssapi = importlib.import_module('gssapi')
        requirement_flag = gssapi.raw.types.RequirementFlag

        # Get the user's Kerberos credentials. Make sure they are from,
        # the FNAL.GOV realm and they haven't expired.

        creds = gssapi.creds.Credentials(usage='initiate')
        principal = str(creds.name).split('@')

        if principal[1] != 'FNAL.GOV':
            raise ValueError('invalid Kerberos realm')
        if creds.lifetime <= 0:
            raise ValueError('Kerberos ticket expired')

        try:
            async with self._state_sem as lock:

                # Create a security context used to sign messages.

                msg = await self._auth_step(lock, None)
                service_name = gssapi.Name(msg.serviceName.translate(
                    {ord('@'): '/', ord('\\'): None}))
                _log.info('service name: %s', service_name)
                ctx = gssapi.SecurityContext(name=service_name, usage='initiate',
                                             creds=creds,
                                             flags=[requirement_flag.replay_detection,
                                                    requirement_flag.integrity,
                                                    requirement_flag.out_of_sequence_detection],
                                             mech=gssapi.MechType.kerberos)
                try:
                    if role is not None:
                        await self._add_to_list(lock, 0, f'#ROLE:{role}')

                    # Enter a loop which steps the security context to
                    # completion (or an error occurs.)

                    in_tok = None
                    while not ctx.complete:
                        msg = await self._auth_step(lock, bytes(ctx.step(in_tok)))

                        if not hasattr(msg, 'token'):
                            break

                        in_tok = msg.token

                    # Now that the context has been validated, send
                    # the 'EnableSettings' request with a signed
                    # message.

                    msg = EnableSettings_request()
                    msg.list_id = 0
                    msg.message = b'1234'
                    msg.MIC = ctx.get_signature(msg.message)

                    await self._mk_request(lock, msg)
                    self.can_set = True
                    _log.info('settings enabled')
                finally:
                    del ctx
        finally:
            del creds

    async def apply_settings(self, input_array):
        """A placeholder for apply setting docstring
        """

        async with self._state_sem as lock:
            if not self.can_set:
                raise RuntimeError('settings are disabled')

            if not isinstance(input_array, list):
                input_array = [input_array]

            msg = ApplySettings_request()

            for ref_id, input_val in input_array:
                if self._dev_list.get(ref_id) is None:
                    raise ValueError(f'setting for undefined ref_id, {ref_id}')

                dpm_struct = DPM._build_struct(ref_id, input_val)
                if isinstance(dpm_struct, RawSetting_struct):
                    if not hasattr(msg, 'raw_array'):
                        msg.raw_array = []
                    msg.raw_array.append(dpm_struct)
                elif isinstance(dpm_struct, TextSetting_struct):
                    if not hasattr(msg, 'text_array'):
                        msg.text_array = []
                    msg.text_array.append(dpm_struct)
                else:
                    if not hasattr(msg, 'scaled_array'):
                        msg.scaled_array = []
                    msg.scaled_array.append(dpm_struct)

            msg.list_id = 0
            await self._mk_request(lock, msg)


class DPMContext:
    """Creates a communication context with one DPM (of a pool of DPMs.)
This context must be used in an `async-with-statement` so that
resources are properly released when the block is exited.

    async with DpmContext() as dpm:
        # 'dpm' is an instance of DPM and is usable while
        # in this block.

Creating a DPM context isn't necessarily a trivial process, so it
should be done at a higher level - preferrably as the script starts
up. If a specific DPM node isn't required, the context will do a
service discovery to choose an available DPM. Future versions of this
package may move the Kerberos negotiation into this section as well,
instead of hiding it in `.settings_enable()`, so it will be even more
expensive.

    """

    def __init__(self, *, port=6805):
        self.dpm = DPM(port)

    async def __aenter__(self):
        _log.debug('entering DPM context')
        await self.dpm.connect()
        return self.dpm

    async def __aexit__(self, exc_type, exc, trace_back):
        _log.debug('exiting DPM context')
        await self.dpm._shutdown_state()
        return False
