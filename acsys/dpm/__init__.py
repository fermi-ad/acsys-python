import datetime
import asyncio
import gssapi
from gssapi.raw.types import RequirementFlag
import logging
import acsys.dpm.dpm_protocol
from acsys.dpm.dpm_protocol import (ServiceDiscovery_request, OpenList_request,
                                    AddToList_request, RemoveFromList_request,
                                    StartList_request, StopList_request,
                                    ClearList_request, RawSetting_struct,
                                    TextSetting_struct, ScaledSetting_struct,
                                    ApplySettings_request, Status_reply,
                                    AnalogAlarm_reply, BasicStatus_reply,
                                    DigitalAlarm_reply, DeviceInfo_reply,
                                    Raw_reply, ScalarArray_reply, Scalar_reply,
                                    TextArray_reply, Text_reply,
                                    ListStatus_reply, ApplySettings_reply,
                                    Authenticate_request, EnableSettings_request)

_log = logging.getLogger('acsys')

class _ItemCommon:
    """Base class that defines common attributes of ItemData and
ItemStatus."""

    def __init__(self, tag):
        self._tag = tag

    @property
    def tag(self):
        return self._tag

    def isReadingFor(self, tag):
        return False

    def isStatusFor(self, tag):
        return False

class ItemData(_ItemCommon):
    """An object that holds a reading from a device.

DPM delivers device data using a stream of ItemData objects. The 'tag'
field corresponds to the tag parameter used when the '.add_entry()'
method was used to add the device to the list.

The 'stamp' field is the timestamp when the data occurred.

The 'data' field is the requested data. The data will be of the type
asked in the corresponding DRF2 (specified in the call to the
'.add_entry()' method.) For instance, if .RAW was specified, the
'data' field will contain a bytearray(). Otherwise it will contain a
scaled, floating point value (or an array, if it's an array device.)

    """

    def __init__(self, tag, stamp, data, micros=None, meta={}):
        super().__init__(tag)
        delta = datetime.timedelta(seconds=stamp // 1000,
                                   microseconds=(stamp % 1000) * 1000 + \
                                                (micros or 0))
        tz = datetime.timezone.utc

        self.stamp = datetime.datetime(1970, 1, 1, tzinfo=tz) + delta
        self.data = data
        self.meta = meta

    def __str__(self):
        return f'{{ tag: {self.tag}, stamp: {self.stamp}, data: {self.data}, meta: {self.meta} }}'

    def isReadingFor(self, tag):
        return self.tag == tag

class ItemStatus(_ItemCommon):
    """An object reporting status of an item in a DPM list.

If there was an error in a request, this object will be in the stream
instead of a ItemData object. The 'tag' field corresponds to the tag
parameter used in the call to the '.add_entry()' method.

The 'status' field describes the error that occurred with this item.

If this message appears, there will never be an ItemData object for
the 'tag' until the error condition is fixed and the list restarted.

    """

    def __init__(self, tag, status):
        super().__init__(tag)
        self.status = acsys.status.Status(status)

    def __str__(self):
        return f'{{ tag: {self.tag}, status: {self.status} }}'

    def isStatusFor(self, tag):
        return self.tag == tag

async def find_dpm(con, *, node=None):
    """Use Service Discovery to find an available DPM.

Multicasts a discovery message to find the next available DPM. The
first responder's node name is returned. If no DPMs are running or an
error occurred while querying, None is returned.

    """

    # The "(node or 'MCAST')" expression is very similar to ternary
    # operators in other languages. If 'node' is None, it is treated
    # as False in the expression so the result is the second operand
    # (i.e. 'MCAST'.) If 'node' is not None, then the expression is
    # equal to it.
    #
    # In other words, if the optional 'node' parameter isn't
    # specified, the task is 'DPMD@MCAST'. If it is specified, the
    # task is ('DPMD@' + node).

    task = 'DPMD@' + (node or 'MCAST')
    msg = ServiceDiscovery_request()
    try:
        replier, _ = await con.request_reply(task, msg, timeout=150,
                                             proto=dpm_protocol)
        return (await con.get_name(replier))
    except acsys.status.Status as e:
        # An ACNET UTIME status is what we receive when no replies
        # have been received in 150ms. This is a valid status (i.e. no
        # DPMs are running), so we consume it and return 'None'.
        # Other fatal errors percolate up.

        if e != acsys.status.ACNET_UTIME:
            raise
        else:
            return None

async def available_dpms(con):
    """Find active DPMs.

This function returns a list of available DPM nodes. If no DPMs are
running, the list will be empty.

    """
    result = []
    msg = ServiceDiscovery_request()
    gen = con.request_stream('DPMD@MCAST', msg, proto=dpm_protocol, timeout=150)
    try:
        async for replier, _ in gen:
            result.append(await con.get_name(replier))
    except acsys.status.Status as e:
        # An ACNET UTIME status is what we receive when no replies
        # have been received in 150ms. This is a valid status (i.e.
        # all DPMs have already responded), so we consume it. Other
        # fatal errors percolate up.

        if e != acsys.status.ACNET_UTIME:
            raise
    return result

class DPM:
    def __init__(self, con, node):
        # These properties can be accessed without owning '_state_sem'
        # because they're either constant or they're not manipulated
        # across 'await' statements.

        self.desired_node = node or 'MCAST'
        self.con = con
        self.meta = {}

        self._state_sem = asyncio.Semaphore()

        # When accessing these properties, '_state_sem' must be owned.

        self.dpm_task = None
        self.list_id = None
        self._dev_list = {}
        self._qrpy = []
        self.gen = None
        self.active = False
        self.can_set = False

    def _xlat_reply(self, msg):
        if isinstance(msg, Status_reply):
            return ItemStatus(msg.ref_id, msg.status)
        elif isinstance(msg, (AnalogAlarm_reply, BasicStatus_reply,
                              DigitalAlarm_reply, Raw_reply,
                              ScalarArray_reply, Scalar_reply,
                              TextArray_reply, Text_reply)):
            return ItemData(msg.ref_id, msg.timestamp, msg.data,
                            meta=self.meta.get(msg.ref_id, {}))
        elif isinstance(msg, ApplySettings_reply):
            for reply in msg.status:
                self._qrpy.append(ItemStatus(reply.ref_id, reply.status))
            return self._qrpy.pop(0) if len(self._qrpy) > 0 else None
        elif isinstance(msg, ListStatus_reply):
            return None
        elif isinstance(msg, DeviceInfo_reply):
            self.meta[msg.ref_id] = \
                { 'di': msg.di, 'name': msg.name,
                  'desc': msg.description,
                  'units': msg.units if hasattr(msg, 'units') else None,
                  'format_hint': msg.format_hint if hasattr(msg, 'format_hint') else None }
        else:
            return msg

    def __aiter__(self):
        return self

    async def __anext__(self):
        while True:
            try:
                if len(self._qrpy) > 0:
                    return self._qrpy.pop(0)
                else:
                    _, msg = await self.gen.__anext__()
                    msg = self._xlat_reply(msg)

                    # If the message is not None, return it. If it is
                    # None, start at the top of the loop.

                    if not (msg is None):
                        return msg
                    else:
                        continue
            except acsys.status.Status as e:

                # If we're disconnected from ACNET, re-throw the
                # exception because there's more work to be done to
                # restore the state of the program.

                if e == acsys.status.ACNET_DISCONNECTED:
                    raise

            # If we've reached here, DPM returned a fatal ACNET
            # status. Whatever it was, we need to pick another DPM and
            # add all the current requests.

            _log.warning('DPM(id: %s) connection closed ... retrying',
                         str(self.list_id))
            await self._restore_state()

    async def _restore_state(self):
        async with self._state_sem as lock:
            await self._connect(lock)
            self._qrpy = []
            if self.can_set:
                self.enable_settings()
            for tag, drf in self._dev_list.items():
                await self._add_to_list(lock, tag, drf)
            if self.active:
                await self.start()

    async def _find_dpm(self, lock):
        dpm = await find_dpm(self.con, node=self.desired_node)

        if not (dpm is None):
            task = 'DPMD@' + dpm
            self.dpm_task = await self.con.make_canonical_taskname(task)
            _log.info('using DPM task: %s', task)
        else:
            self.dpm_task = None

    async def _connect(self, lock):
        await self._find_dpm(lock)

        # Send an OPEN LIST request to the DPM.

        gen = self.con.request_stream(self.dpm_task, OpenList_request(),
                                      proto=dpm_protocol)
        _, msg = await gen.asend(None)
        _log.info('DPM returned list id %d', msg.list_id)

        # Update object state.

        self.gen = gen
        self.list_id = msg.list_id

    def get_entry(self, tag):
        """Returns the DRF string associated with the 'tag'.
        """
        self._dev_list.get(tag)

    async def clear_list(self):
        """Clears all entries in the tag/drf dictionary.

Clearing the list doesn't stop incoming replies. After clearing the
list, either '.stop()' or '.start()' needs to be called.

        """

        msg = ClearList_request()

        async with self._state_sem:
            _log.debug('DPM(id: %d) clearing list', self.list_id)
            msg.list_id = self.list_id
            _, msg = await self.con.request_reply(self.dpm_task, msg,
                                                  proto=dpm_protocol)
            sts = acsys.status.Status(msg.status)

            if sts.isFatal:
                raise sts

            # DPM has been updated so we can safely clear the dictionary.

            self._dev_list = {}

    async def _add_to_list(self, lock, tag, drf):
        msg = AddToList_request()

        msg.list_id = self.list_id
        msg.ref_id = tag
        msg.drf_request = drf

        # Perform the request. If the request returns a fatal error,
        # the status will be raised for us. If the DPM returns a fatal
        # status in the reply message, we raise it ourselves.

        _log.debug('DPM(id: %d) adding tag:%d, drf:%s', self.list_id, tag, drf)
        _, msg = await self.con.request_reply(self.dpm_task, msg,
                                              proto=dpm_protocol)
        sts = acsys.status.Status(msg.status)

        if sts.isFatal:
            raise sts

        # DPM has been updated so we can safely add the entry to our
        # device list.

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

This is just a convenience function to add a list of tag/drf pairs to
a DPM list. If any of the entries is badly formed, an exception will
be raised and the state of DPM will be in a part state of success.

A future version of the DPM protocol will make this method much more
reliable while maintaining its speed.

        """
        async with self._state_sem as lock:
            for tag, drf in entries:
                if isinstance(tag, int):
                    if isinstance(drf, str):
                        await self._add_to_list(lock, tag, drf)
                    else:
                        raise ValueError('drf must be a string')
                else:
                    raise ValueError('tag must be an integer')

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

            async with self._state_sem:
                msg.list_id = self.list_id
                msg.ref_id = tag

                _log.debug('DPM(id: %d) removing tag:%d', self.list_id, tag)
                _, msg = await self.con.request_reply(self.dpm_task, msg,
                                                      proto=dpm_protocol)
                sts = acsys.status.Status(msg.status)

                if sts.isFatal:
                    raise sts

                # DPM has been updated so we can safely remove the
                # entry from our device list.

                del self._dev_list[tag]
        else:
            raise ValueError('tag must be an integer')

    async def _start(self, lock):
        _log.debug('DPM(id: %d) starting list', self.list_id)
        msg = StartList_request()
        msg.list_id = self.list_id
        _, msg = await self.con.request_reply(self.dpm_task, msg,
                                              proto=dpm_protocol)

        sts = acsys.status.Status(msg.status)
        if sts.isFatal:
            raise sts
        self.active = True

    async def start(self):
        """Start/restart data acquisition using the current request list.

Calls to '.add_entry()' and '.remove_entry()' make changes to the list
of requests but don't actually affect data acquisition until this
method is called. This allows a script to make major adjustments and
then enable the changes all at once.

        """

        async with self._state_sem as lock:
            await self._start(lock)

    async def stop(self):
        """Stops data acquisition.

This method stops data acquisition. The list of requests is unaffected
so a call to '.start()' will restart the list.

Due to the asynchronous nature of network communications, after
calling this method, a few readings may still get delivered.

        """

        msg = StopList_request()

        async with self._state_sem:
            _log.debug('DPM(id: %d) stopping list', self.list_id)
            msg.list_id = self.list_id
            _, msg = await self.con.request_reply(self.dpm_task, msg,
                                                  proto=dpm_protocol)
            sts = acsys.status.Status(msg.status)

            if sts.isFatal:
                raise sts
            self.active = False

    async def _shutdown(self):
        if self.gen:
            await self.gen.aclose()

    @staticmethod
    def _build_struct(ref_id, value):
        if isinstance(value, bytearray):
            set_struct = RawSetting_struct()
        elif isinstance(value, str):
            set_struct = TextSetting_struct()
        else:
            if not isinstance(value, list):
                value = [value]
            set_struct = ScaledSetting_struct()

        set_struct.ref_id = ref_id
        set_struct.data = value
        return set_struct

    async def enable_settings(self):
        """Enable settings for the current DPM session.

This method exchanges credentials with the DPM. If successful, the
session is allowed to make settings. The script must be running in an
environment with a valid Kerberos ticket. The ticket must part of the
FNAL.GOV realm and can't be expired.

The credentials are valid as long as this session is maintained.

        """

        # Get the user's Kerberos credentials. Make sure they are from,
        # the FNAL.GOV realm and they haven't expired.

        creds = gssapi.creds.Credentials(usage='initiate')
        principal = str(creds.name).split('@')

        if principal[1] != 'FNAL.GOV':
            raise ValueError('invalid Kerberos domain')
        elif creds.lifetime <= 0:
            raise ValueError('Kerberos ticket expired')

        try:
            # Create a security context used to sign messages.

            service_name = gssapi.Name('daeset/bd/dmq.fnal.gov')
            ctx = gssapi.SecurityContext(name=service_name, usage='initiate',
                                         creds=creds,
                                         flags=[RequirementFlag.replay_detection,
                                                RequirementFlag.integrity,
                                                RequirementFlag.out_of_sequence_detection],
                                         mech=gssapi.MechType.kerberos)
            try:
                async with self._state_sem:

                    # First send an Authentication request so DPM can
                    # validate the context.

                    msg = Authenticate_request()
                    msg.list_id = self.list_id
                    msg.token = ctx.step()

                    _, reply = await self.con.request_reply(self.dpm_task, msg,
                                                            proto=dpm_protocol)

                    # Now that the context has been validated, send
                    # the 'EnableSettings' request with a signed
                    # messages.

                    msg = EnableSettings_request()
                    msg.list_id = self.list_id
                    msg.message = b'1234'
                    msg.MIC = ctx.get_signature(msg.message)

                    _, reply = await self.con.request_reply(self.dpm_task, msg,
                                                            proto=dpm_protocol)

                    self.can_set = True
                    _log.info('DPM(id: %d) settings enabled', self.list_id)
            finally:
                del ctx
        finally:
            del creds

    async def apply_settings(self, input_array):
        """A placeholder for apply setting docstring
        """

        async with self._state_sem:
            if not self.can_set:
                raise RuntimeError('settings are disabled')

            if not isinstance(input_array, list):
                input_array = [input_array]

            msg = ApplySettings_request()

            for ref_id, input_val in input_array:
                if self._dev_list.get(ref_id) is None:
                    raise ValueError(f'setting for undefined ref_id, {ref_id}')

                s = DPM._build_struct(ref_id, input_val)
                if isinstance(s, RawSetting_struct):
                    if not hasattr(msg, 'raw_array'):
                        msg.raw_array = []
                    msg.raw_array.append(s)
                elif isinstance(s, TextSetting_struct):
                    if not hasattr(msg, 'text_array'):
                        msg.text_array = []
                    msg.text_array.append(s)
                else:
                    if not hasattr(msg, 'scaled_array'):
                        msg.scaled_array = []
                    msg.scaled_array.append(s)

            msg.list_id = self.list_id

            _, reply = await self.con.request_reply(self.dpm_task, msg,
                                                    proto=dpm_protocol)

            sts = acsys.status.Status(reply.status)
            if sts.isFatal:
                raise sts

class DPMContext:
    def __init__(self, con, *, dpm_node=None):
        self.dpm = DPM(con, dpm_node)

    async def __aenter__(self):
        _log.debug('entering DPM context')
        await self.dpm._restore_state()
        return self.dpm

    async def __aexit__(self, exc_type, exc, tb):
        _log.debug('exiting DPM context')
        await self.dpm._shutdown()
        return False
