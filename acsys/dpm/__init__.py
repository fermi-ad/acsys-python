import datetime
import asyncio
import logging
import acsys.dpm.dpm_protocol
from acsys.dpm.dpm_protocol import (ServiceDiscovery_request, OpenList_request,
                                    AddToList_request, RemoveFromList_request,
                                    StartList_request, StopList_request,
                                    ClearList_request)

_log = logging.getLogger('asyncio')

class ItemData:
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

    def __init__(self, tag, stamp, cycle, data, micros=None):
        self.tag = tag
        self.stamp = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc) + \
                     datetime.timedelta(seconds=stamp // 1000,
                                        milliseconds=stamp % 1000)
        self.data = data
        self.cycle = cycle
        if not micros is None:
            self.micros = micros

    def __str__(self):
        guaranteed_fields = f'{{ tag: {self.tag}, stamp: {self.stamp}, data: {self.data}'
        if hasattr(self, 'micros'):
            return guaranteed_fields + f', micros: {self.micros}'
        return guaranteed_fields + ' }'

class ItemStatus:
    """An object reporting status of an item in a DPM list.

If there was an error in a request, this object will be in the stream
instead of a ItemData object. The 'tag' field corresponds to the tag
parameter used in the call to the '.add_entry()' method.

The 'status' field describes the error that occurred with this item.

If this message appears, there will never be an ItemData object for
the 'tag' until the error condition is fixed and the list restarted.

    """

    def __init__(self, tag, status):
        self.tag = tag
        self.status = status

    def __str__(self):
        return f'{tag: {self.tag}, status: {self.status}}'

# Since Python doesn't yet have `itertools` for async generators, we
# kludge it by highjacking the unmarshal routine in our multiple reply
# request. This function will be called for each incoming packet. We
# first call the underlying protocol compiler routine to translate it
# and then transform certain reply messages into `ItemData` and
# `ItemStatus` types.

def unmarshal_reply(ii):
    """This is a function that needs to be exported, but should be
    considered private.

    """
    msg = dpm_protocol.unmarshal_reply(ii)
    if isinstance(msg, dpm_protocol.Status_reply):
        return ItemStatus(msg.ref_id, acnet.status.Status(msg.status))
    elif isinstance(msg, (dpm_protocol.AnalogAlarm_reply,
                          dpm_protocol.BasicStatus_reply,
                          dpm_protocol.DigitalAlarm_reply,
                          dpm_protocol.Raw_reply,
                          dpm_protocol.ScalarArray_reply,
                          dpm_protocol.Scalar_reply,
                          dpm_protocol.TextArray_reply,
                          dpm_protocol.Text_reply)):
        return ItemData(msg.ref_id, msg.timestamp, msg.cycle, msg.data)
    else:
        return msg

async def find_dpm(con, *, node=None):
    """Use Service Discovery to find an available DPM.

Multicasts a discovery message to find the next available DPM. The
first responder's node name is returned. If no DPMs are running or an
error occurred while querying, None is returned.

    """

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

This function returns a list of available DPM nodes.

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

class DPM():
    def __init__(self, con, node):
        self.desired_node = node or 'MCAST'
        self.dpm_task = None
        self.list_id = None
        self._dev_list_sem = asyncio.Semaphore()
        self._dev_list = {}
        self.con = con
        self.gen = None

    async def __aiter__(self):
        return self.gen

    async def _find_dpm(self):
        dpm = await find_dpm(self.con, node=self.desired_node)

        if not (dpm is None):
            self.dpm_task = 'DPMD@' + dpm
            _log.info('using DPM task: %s', self.dpm_task)
        else:
            self.dpm_task = None

    async def _connect(self):
        await self._find_dpm()

        # Send an OPEN LIST request to the DPM.

        gen = self.con.request_stream(self.dpm_task, OpenList_request(),
                                      proto=acsys.dpm)
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
        msg.list_id = self.list_id

        async with self._dev_list_sem:
            _log.debug('clearing list:%d', msg.list_id)
            _, msg = await self.con.request_reply(self.dpm_task, msg,
                                                  proto=dpm_protocol)
            sts = acsys.status.Status(msg.status)

            if sts.isFatal:
                raise sts

            # DPM has been updated so we can safely clear the dictionary.

            self._dev_list = {}

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
                # Create the message and set the fields appropriately.

                msg = AddToList_request()

                msg.list_id = self.list_id
                msg.ref_id = tag
                msg.drf_request = drf

                async with self._dev_list_sem:
                    # Perform the request. If the request returns a
                    # fatal error, the status will be raised for
                    # us. If the DPM returns a fatal status in the
                    # reply message, we raise it ourselves.

                    _log.debug('adding tag:%d, drf:%s to list:%d', tag, drf,
                               msg.list_id)
                    _, msg = await self.con.request_reply(self.dpm_task, msg,
                                                          proto=dpm_protocol)
                    sts = acsys.status.Status(msg.status)

                    if sts.isFatal:
                        raise sts

                    # DPM has been updated so we can safely add the
                    # entry to our device list.

                    self._dev_list[tag] = drf
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
        for tag, drf in entries:
            await self.add_entry(tag, drf)

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

            msg.list_id = self.list_id
            msg.ref_id = tag

            async with self._dev_list_sem:
                _log.debug('removing tag:%d from list:%d', tag, msg.list_id)
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

    async def start(self):
        """Start/restart data acquisition using the current request list.

Calls to '.add_entry()' and '.remove_entry()' make changes to the list
of requests but don't actually affect data acquisition until this
method is called. This allows a script to make major adjustments and
then enable the changes all at once.

        """

        msg = StartList_request()

        msg.list_id = self.list_id

        async with self._dev_list_sem:
            _log.debug('starting list %d', msg.list_id)
            _, msg = await self.con.request_reply(self.dpm_task, msg,
                                                  proto=dpm_protocol)
            sts = acsys.status.Status(msg.status)

            if sts.isFatal:
                raise sts

    async def stop(self):
        """Stops data acquisition.

This method stops data acquisition. The list of requests is unaffected
so a call to '.start()' will restart the list.

Due to the asynchronous nature of network communications, after
calling this method, a few readings may still get delivered.

        """

        msg = StopList_request()

        msg.list_id = self.list_id

        async with self._dev_list_sem:
            _log.debug('stopping list %d', msg.list_id)
            _, msg = await self.con.request_reply(self.dpm_task, msg,
                                                  proto=dpm_protocol)
            sts = acsys.status.Status(msg.status)

            if sts.isFatal:
                raise sts

    async def _shutdown(self):
        await self.gen.aclose()

class DPMContext():
    def __init__(self, con, *, dpm_node=None):
        self.dpm = DPM(con, dpm_node)

    async def __aenter__(self):
        _log.debug('entering DPM context')
        await self.dpm._connect()
        return self.dpm

    async def __aexit__(self, exc_type, exc, tb):
        _log.debug('exiting DPM context')
        await self.dpm._shutdown()
        return False
